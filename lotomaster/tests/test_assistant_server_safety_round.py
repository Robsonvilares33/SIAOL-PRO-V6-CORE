import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from lotomaster.api import app
from lotomaster.assistant import build_assistant_report
from lotomaster.assistant_access import SlidingWindowRateLimiter


TOKEN = "lotomaster-test-token-" + "x" * 32


class ServerAssistantSafetyTests(unittest.TestCase):
    def setUp(self):
        self.draw = {"game": "megasena", "contest": 50, "numbers": [1, 2, 3, 4, 5, 6]}
        self.client = TestClient(app)

    def test_server_gemini_routes_are_closed_by_default(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fake"}, clear=True), \
             patch("lotomaster.assistant.requests.post") as post, \
             patch("lotomaster.api.list_results", return_value=[self.draw]):
            get = self.client.get("/api/v1/megasena/assistant?use_gemini=true")
            result = self.client.post(
                "/api/v1/megasena/assistant/from-draws",
                json={"draws": [self.draw], "use_gemini": True},
            )
        self.assertEqual(get.status_code, 503)
        self.assertEqual(result.status_code, 503)
        post.assert_not_called()

    def test_routes_reject_missing_and_wrong_server_tokens(self):
        env = {
            "GEMINI_API_KEY": "fake-provider-key",
            "LOTOMASTER_ENABLE_SERVER_GEMINI": "true",
            "LOTOMASTER_SERVER_GEMINI_TOKEN": TOKEN,
        }
        with patch.dict("os.environ", env, clear=True), \
             patch("lotomaster.api.build_assistant_report") as build, \
             patch("lotomaster.api.list_results", return_value=[self.draw]):
            missing = self.client.get("/api/v1/megasena/assistant?use_gemini=true")
            wrong = self.client.post(
                "/api/v1/megasena/assistant/from-draws",
                json={"draws": [self.draw], "use_gemini": True},
                headers={"Authorization": "Bearer wrong-token"},
            )
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(missing.headers["www-authenticate"], "Bearer")
        build.assert_not_called()

    def test_configured_routes_accept_authorized_call_and_rate_limit(self):
        env = {
            "GEMINI_API_KEY": "fake-provider-key",
            "LOTOMASTER_ENABLE_SERVER_GEMINI": "true",
            "LOTOMASTER_SERVER_GEMINI_TOKEN": TOKEN,
        }
        limiter = SlidingWindowRateLimiter(per_client_limit=1, global_limit=10)
        headers = {"Authorization": f"Bearer {TOKEN}"}
        with patch.dict("os.environ", env, clear=True), \
             patch("lotomaster.assistant_access.server_gemini_rate_limiter", limiter), \
             patch("lotomaster.api.build_assistant_report", return_value={"ai": {"status": "available"}}) as build, \
             patch("lotomaster.api.list_results", return_value=[self.draw]):
            authorized = self.client.get("/api/v1/megasena/assistant?use_gemini=true", headers=headers)
            limited = self.client.get("/api/v1/megasena/assistant?use_gemini=true", headers=headers)
            build.assert_called_once_with("megasena", [self.draw], use_gemini=True)
        self.assertEqual(authorized.status_code, 200)
        self.assertEqual(limited.status_code, 429)
        self.assertIn("retry-after", limited.headers)

    def test_incomplete_or_weak_access_configuration_stays_closed(self):
        for token in ("short", "fake-provider-key"):
            with self.subTest(token=token), patch.dict(
                "os.environ",
                {
                    "GEMINI_API_KEY": "fake-provider-key",
                    "LOTOMASTER_ENABLE_SERVER_GEMINI": "true",
                    "LOTOMASTER_SERVER_GEMINI_TOKEN": token,
                },
                clear=True,
            ):
                response = self.client.get(
                    "/api/v1/megasena/assistant?use_gemini=true",
                    headers={"Authorization": f"Bearer {token}"},
                )
                self.assertEqual(response.status_code, 503)

    def test_valid_length_access_token_equal_to_provider_key_is_rejected(self):
        shared = "A" * 40
        env = {
            "GEMINI_API_KEY": shared,
            "LOTOMASTER_ENABLE_SERVER_GEMINI": "true",
            "LOTOMASTER_SERVER_GEMINI_TOKEN": shared,
        }
        with patch.dict("os.environ", env, clear=True), \
             patch("lotomaster.api.build_assistant_report") as build, \
             patch("lotomaster.api.list_results", return_value=[self.draw]):
            response = self.client.get(
                "/api/v1/megasena/assistant?use_gemini=true",
                headers={"Authorization": f"Bearer {shared}"},
            )
        self.assertEqual(response.status_code, 503)
        build.assert_not_called()

    def test_model_response_has_independent_disclaimer(self):
        response = Mock()
        response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Interpretação do modelo."}]}}]}
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fake", "LOTOMASTER_ENABLE_SERVER_GEMINI": "true"}, clear=True), \
             patch("lotomaster.assistant.requests.post", return_value=response):
            report = build_assistant_report("megasena", [self.draw], use_gemini=True)
        self.assertEqual(report["ai"]["status"], "available")
        self.assertIn("Interpretação do modelo.", report["commentary"])
        self.assertIn("não são probabilidades futuras", report["commentary"])

    def test_failed_provider_is_explicitly_identified(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fake", "LOTOMASTER_ENABLE_SERVER_GEMINI": "true"}, clear=True), \
             patch("lotomaster.assistant.requests.post", side_effect=RuntimeError("fail")):
            report = build_assistant_report("megasena", [self.draw], use_gemini=True)
        self.assertEqual(report["ai"]["status"], "temporarily_unavailable")
        self.assertEqual(report["ai"]["attempted_provider"], "Google Gemini")
        self.assertEqual(report["ai"]["provider"], "análise local explicável")
        self.assertIn("não probabilidades calibradas", report["commentary"])


class SlidingWindowRateLimiterTests(unittest.TestCase):
    def test_applies_per_client_and_global_limits_then_expires(self):
        limiter = SlidingWindowRateLimiter(per_client_limit=2, global_limit=3, window_seconds=60)
        self.assertIsNone(limiter.consume("a", now=0))
        self.assertIsNone(limiter.consume("a", now=1))
        self.assertEqual(limiter.consume("a", now=2), 58)
        self.assertIsNone(limiter.consume("b", now=3))
        self.assertEqual(limiter.consume("c", now=4), 56)
        self.assertIsNone(limiter.consume("a", now=61))


if __name__ == "__main__":
    unittest.main()
