import http.client
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from lotomaster import mcp_server, storage


TOKEN = "test-only-mcp-token-0123456789-abcdefghijklmnopqrstuvwxyz"


class MCPHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_token = os.environ.get("LOTOMASTER_MCP_BEARER_TOKEN")
        os.environ["LOTOMASTER_MCP_BEARER_TOKEN"] = TOKEN
        cls.server = mcp_server.BoundedMCPHTTPServer(("127.0.0.1", 0), mcp_server.MCPHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.host, cls.port = cls.server.server_address

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        if cls._old_token is None:
            os.environ.pop("LOTOMASTER_MCP_BEARER_TOKEN", None)
        else:
            os.environ["LOTOMASTER_MCP_BEARER_TOKEN"] = cls._old_token

    def post(self, payload, *, token=TOKEN, origin=None, accept="application/json, text/event-stream"):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        headers = {"Content-Type": "application/json", "Accept": accept}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        if origin is not None:
            headers["Origin"] = origin
        connection.request("POST", mcp_server.MCP_PATH, json.dumps(payload), headers)
        response = connection.getresponse()
        body = response.read()
        status = response.status
        response_headers = dict(response.getheaders())
        connection.close()
        return status, response_headers, body

    def test_authentication_required_and_token_not_echoed(self):
        status, _, body = self.post({"jsonrpc": "2.0", "id": 1, "method": "ping"}, token=None)
        self.assertEqual(status, 401)
        self.assertNotIn(TOKEN.encode(), body)
        status, _, body = self.post({"jsonrpc": "2.0", "id": 1, "method": "ping"}, token="wrong-token")
        self.assertEqual(status, 401)
        self.assertNotIn(TOKEN.encode(), body)

    def test_origin_and_accept_validation(self):
        status, _, _ = self.post({"jsonrpc": "2.0", "id": 1, "method": "ping"}, origin="https://attacker.example")
        self.assertEqual(status, 403)
        status, _, _ = self.post({"jsonrpc": "2.0", "id": 1, "method": "ping"}, accept="application/json")
        self.assertEqual(status, 406)

    def test_initialize_tools_and_notification(self):
        status, _, body = self.post({
            "jsonrpc": "2.0", "id": 7, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
        })
        self.assertEqual(status, 200)
        initialize = json.loads(body)["result"]
        self.assertEqual(initialize["protocolVersion"], "2025-03-26")
        self.assertIn("tools", initialize["capabilities"])
        status, _, body = self.post({
            "jsonrpc": "2.0", "id": 9, "method": "initialize",
            "params": {"protocolVersion": ["invalid"]},
        })
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["result"]["protocolVersion"], mcp_server.MCP_PROTOCOL_VERSION)
        status, _, body = self.post({"jsonrpc": "2.0", "id": 8, "method": "tools/list"})
        self.assertEqual(status, 200)
        names = {tool["name"] for tool in json.loads(body)["result"]["tools"]}
        self.assertEqual(names, {
            "lottery_catalog", "get_lottery_rules", "read_history", "analyze_draws",
            "calculate_ticket_probability", "generate_ticket_preview", "list_project_files",
            "read_project_file", "analyze_games",
        })
        status, _, body = self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(status, 202)
        self.assertEqual(body, b"")

    def test_analysis_and_probability_tools(self):
        status, _, body = self.post({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "analyze_draws", "arguments": {
                "game": "lotofacil", "draws": [{"contest": 1, "numbers": list(range(1, 16))}],
            }},
        })
        self.assertEqual(status, 200)
        analysis = json.loads(body)["result"]["structuredContent"]
        self.assertFalse(analysis["persisted"])
        self.assertIn("origem não autenticada", analysis["source"])
        status, _, body = self.post({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "calculate_ticket_probability", "arguments": {"game": "megasena"}},
        })
        self.assertEqual(status, 200)
        result = json.loads(body)["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["probability"]["one_in"], 50063860)

    def test_unexpected_origin_and_token_configuration_fail_closed(self):
        with patch.dict(os.environ, {"LOTOMASTER_MCP_BEARER_TOKEN": "short"}):
            status, _, body = self.post({"jsonrpc": "2.0", "id": 1, "method": "ping"}, token="short")
        self.assertEqual(status, 503)
        self.assertNotIn(b"short", body)


class MCPReadOnlyTests(unittest.TestCase):
    def test_missing_history_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "absent.sqlite3"
            with patch.object(storage, "DB_PATH", missing):
                with self.assertRaisesRegex(ValueError, "não cria nem busca"):
                    mcp_server._tool_result("read_history", {"game": "lotofacil"})
            self.assertFalse(missing.exists())

    def test_history_is_read_from_existing_db_only(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "history.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE lottery_draws (game TEXT, contest INTEGER, payload TEXT)")
                connection.execute(
                    "INSERT INTO lottery_draws(game, contest, payload) VALUES(?, ?, ?)",
                    ("lotofacil", 12, json.dumps({"game": "lotofacil", "contest": 12, "numbers": list(range(1, 16))})),
                )
            with patch.object(storage, "DB_PATH", database):
                result = mcp_server._tool_result("read_history", {"game": "lotofacil", "limit": 20})
            self.assertEqual(result["count"], 1)
            self.assertFalse(result["verified_officially"])
            with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM lottery_draws").fetchone()[0], 1)

    def test_generated_preview_does_not_touch_database(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "not-created.sqlite3"
            with patch.object(storage, "DB_PATH", missing):
                result = mcp_server._tool_result("generate_ticket_preview", {
                    "game": "lotofacil", "count": 3, "seed": 77,
                })
                second = mcp_server._tool_result("generate_ticket_preview", {
                    "game": "lotofacil", "count": 3, "seed": 77,
                })
            self.assertEqual(result["count"], 3)
            self.assertFalse(result["persisted"])
            self.assertEqual(len(result["items"][0]["numbers"]), 15)
            self.assertEqual(result["items"], second["items"])
            self.assertFalse(missing.exists())

    def test_project_file_listing_redacts_secrets_and_blocks_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            (root / "app.py").write_text(
                'api_key = "sk-abcdefghijklmnopqrstuvwxyz0123456789"\n'
                'authorization = "Bearer 0123456789abcdefghijklmnopqrstuvwxyz"\n'
                'session_token = generic-secret-value-not-a-known-token-prefix\n'
                'description = "safe text"\n',
                encoding="utf-8",
            )
            (root / ".env").write_text("password='never-list'", encoding="utf-8")
            (root / "notes.txt").write_text("safe", encoding="utf-8")
            (root / "secret_notes.txt").write_text("hidden", encoding="utf-8")
            (root / "cache.sqlite3").write_bytes(b"SQLite format")
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("hidden", encoding="utf-8")
            outside = Path(directory) / "outside.py"
            outside.write_text("outside", encoding="utf-8")
            (root / "outside-link.py").symlink_to(outside)
            with patch.object(mcp_server, "REPO_ROOT", root):
                listing = mcp_server._tool_result("list_project_files", {"limit": 20})
                paths = {item["path"] for item in listing["items"]}
                self.assertEqual(paths, {"app.py", "notes.txt"})
                read = mcp_server._tool_result("read_project_file", {"path": "app.py"})
                text = read["content"]
                self.assertIn("[REDACTED]", text)
                self.assertIn("safe text", text)
                self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz0123456789", text)
                self.assertNotIn("0123456789abcdefghijklmnopqrstuvwxyz", text)
                self.assertNotIn("generic-secret-value-not-a-known-token-prefix", text)
                self.assertNotIn("outside-link.py", paths)
                with self.assertRaisesRegex(ValueError, "fora do escopo"):
                    mcp_server._tool_result("read_project_file", {"path": "outside-link.py"})
                with self.assertRaisesRegex(ValueError, "não está no conjunto permitido"):
                    mcp_server._tool_result("read_project_file", {"path": ".env"})
                with self.assertRaisesRegex(ValueError, "permanecer dentro"):
                    mcp_server._tool_result("read_project_file", {"path": "../outside.txt"})

    def test_redaction_covers_auth_headers_and_query_tokens(self):
        secret = "generic_token_value_0123456789abcdefghijklmnopqrstuvwxyz"
        source = (
            f"Authorization: Bearer {secret}\n"
            f"callback=https://example.test/path?access_token={secret}\n"
            "docs=https://modelcontextprotocol.io/specification/2025-11-25/basic/transports"
        )
        result = mcp_server._redact_sensitive_text(source)
        self.assertNotIn(secret, result)
        self.assertIn("Authorization: [REDACTED]", result)
        self.assertIn("access_token=[REDACTED]", result)
        self.assertIn("https://modelcontextprotocol.io/specification/2025-11-25/basic/transports", result)

    def test_analyze_games_is_bounded_and_non_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "must-not-exist.sqlite3"
            draw = {"game": "lotofacil", "contest": 17, "numbers": list(range(1, 16))}
            ticket = {"numbers": list(range(1, 16))}
            with patch.object(storage, "DB_PATH", missing):
                result = mcp_server._tool_result("analyze_games", {
                    "game": "lotofacil", "tickets": [ticket], "draws": [draw],
                })
                self.assertFalse(missing.exists())
            self.assertFalse(result["persisted"])
            self.assertFalse(result["local_storage_accessed"])
            self.assertEqual(result["analysis"]["evaluated_tickets"], 1)
            self.assertEqual(result["analysis"]["evaluated_contests"], 1)
            with self.assertRaisesRegex(ValueError, "1 a 100 jogos"):
                mcp_server._tool_result("analyze_games", {
                    "game": "lotofacil", "tickets": [ticket] * 101, "draws": [draw],
                })

    def test_stdio_round_trip_needs_no_bearer_and_emits_only_jsonrpc(self):
        payload = (
            '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
            '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
            '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
        )
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True):
            mcp_server.serve_stdio(io.StringIO(payload), output)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([item["id"] for item in responses], [1, 2])
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "lotomaster-mcp")
        self.assertEqual(len(responses[1]["result"]["tools"]), 9)

    def test_stdio_subprocess_starts_without_http_token(self):
        environment = os.environ.copy()
        environment.pop("LOTOMASTER_MCP_BEARER_TOKEN", None)
        completed = subprocess.run(
            [sys.executable, "-m", "lotomaster.mcp_server", "--transport", "stdio"],
            input='{"jsonrpc":"2.0","id":9,"method":"ping"}\n',
            text=True, capture_output=True, cwd=Path(__file__).resolve().parents[2],
            env=environment, timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        self.assertEqual(json.loads(completed.stdout), {"jsonrpc": "2.0", "id": 9, "result": {}})

    def test_resource_describes_non_accessible_browser_data(self):
        response = mcp_server._dispatch({"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": "lotomaster://overview"}})
        text = response["result"]["contents"][0]["text"]
        self.assertIn("localStorage", text)
        self.assertIn("não são visíveis", text)
        self.assertNotIn("LOTOMASTER_MCP_BEARER_TOKEN=", text)


class MCPBranchEditTests(unittest.TestCase):
    def _git(self, root, *arguments):
        return subprocess.run(
            ["git", "-C", str(root), *arguments], check=True,
            capture_output=True, text=True, timeout=10,
        )

    def _repo(self, branch=mcp_server.EDITABLE_BRANCH):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "lotomaster").mkdir()
        target = root / "lotomaster" / "script.py"
        target.write_text("before\n", encoding="utf-8")
        self._git(root, "init", "-q")
        self._git(root, "branch", "-M", branch)
        self._git(root, "config", "user.name", "MCP Test")
        self._git(root, "config", "user.email", "mcp-test@example.invalid")
        self._git(root, "add", "lotomaster/script.py")
        self._git(root, "commit", "-q", "-m", "base")
        return temporary, root, target

    def test_edit_tools_are_opt_in_and_stdio_only(self):
        with patch.dict(os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "0"}):
            disabled = mcp_server._dispatch({"jsonrpc": "2.0", "id": 0, "method": "tools/list"}, transport="stdio")
            disabled_names = {item["name"] for item in disabled["result"]["tools"]}
            self.assertEqual(len(disabled_names), 9)
        with patch.dict(os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"}):
            stdio = mcp_server._dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, transport="stdio")
            stdio_init = mcp_server._dispatch({"jsonrpc": "2.0", "id": 5, "method": "initialize", "params": {}}, transport="stdio")
            http = mcp_server._dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, transport="http")
            stdio_names = {item["name"] for item in stdio["result"]["tools"]}
            http_names = {item["name"] for item in http["result"]["tools"]}
            self.assertTrue({"edit_branch_file", "review_branch_diff", "run_branch_checks"} <= stdio_names)
            self.assertIn("Modo opcional de edição local ativo", stdio_init["result"]["instructions"])
            self.assertEqual(len(http_names), 9)
            self.assertFalse({"edit_branch_file", "review_branch_diff", "run_branch_checks"} & http_names)
            denied = mcp_server._dispatch({
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "edit_branch_file", "arguments": {}},
            }, transport="http")
            self.assertTrue(denied["result"]["isError"])

    def test_edit_uses_expected_hash_and_diff_redacts_sensitive_values(self):
        temporary, root, target = self._repo()
        self.addCleanup(temporary.cleanup)
        original_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        new_content = 'api_key = "sk-abcdefghijklmnopqrstuvwxyz0123456789"\n'
        with patch.object(mcp_server, "REPO_ROOT", root), patch.dict(os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"}):
            result = mcp_server._tool_result("edit_branch_file", {
                "path": "lotomaster/script.py", "expected_sha256": original_hash, "content": new_content,
            }, transport="stdio")
            review = mcp_server._tool_result("review_branch_diff", {}, transport="stdio")
        self.assertTrue(result["changed"])
        self.assertFalse(result["committed"])
        self.assertFalse(result["published"])
        self.assertEqual(target.read_text(encoding="utf-8"), new_content)
        self.assertEqual(list((root / "lotomaster").glob(".lotomaster-mcp-edit-*.tmp")), [])
        self.assertEqual(review["changed_files"], ["lotomaster/script.py"])
        self.assertIn("[REDACTED]", review["diff"])
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz0123456789", review["diff"])

    def test_stale_hash_wrong_branch_and_unsafe_paths_do_not_write(self):
        temporary, root, target = self._repo()
        self.addCleanup(temporary.cleanup)
        with patch.object(mcp_server, "REPO_ROOT", root), patch.dict(os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"}):
            with self.assertRaisesRegex(ValueError, "SHA-256 divergente"):
                mcp_server._tool_result("edit_branch_file", {
                    "path": "lotomaster/script.py", "expected_sha256": "0" * 64, "content": "bad\n",
                }, transport="stdio")
            with self.assertRaisesRegex(ValueError, "canônico"):
                mcp_server._tool_result("edit_branch_file", {
                    "path": "lotomaster/../outside.md", "expected_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "content": "bad\n",
                }, transport="stdio")
            with self.assertRaisesRegex(ValueError, "estudos congelados"):
                mcp_server._tool_result("edit_branch_file", {
                    "path": "lotomaster/AVALIACAO_LOTOMASTER.md", "expected_sha256": "0" * 64, "content": "bad\n",
                }, transport="stdio")
            with self.assertRaisesRegex(ValueError, "estudos congelados"):
                mcp_server._tool_result("edit_branch_file", {
                    "path": "lotomaster/studies/frozen_runner.py", "expected_sha256": "0" * 64, "content": "bad\n",
                }, transport="stdio")
            self.assertFalse(mcp_server._is_editable_branch_path("lotomaster/studies/frozen_runner.py"))
            outside = root / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            (root / "lotomaster" / "link.py").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "Arquivo inexistente"):
                mcp_server._tool_result("edit_branch_file", {
                    "path": "lotomaster/link.py", "expected_sha256": hashlib.sha256(outside.read_bytes()).hexdigest(), "content": "bad\n",
                }, transport="stdio")
            hardlink = root / "lotomaster" / "hardlink.py"
            os.link(target, hardlink)
            with self.assertRaisesRegex(ValueError, "hard links"):
                mcp_server._tool_result("edit_branch_file", {
                    "path": "lotomaster/hardlink.py", "expected_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "content": "bad\n",
                }, transport="stdio")
            self._git(root, "switch", "-c", "main")
            wrong_branch_tools = mcp_server._dispatch(
                {"jsonrpc": "2.0", "id": 4, "method": "tools/list"}, transport="stdio",
            )
            wrong_branch_names = {item["name"] for item in wrong_branch_tools["result"]["tools"]}
            self.assertNotIn("edit_branch_file", wrong_branch_names)
            wrong_branch_init = mcp_server._dispatch(
                {"jsonrpc": "2.0", "id": 6, "method": "initialize", "params": {}}, transport="stdio",
            )
            self.assertNotIn("Modo opcional de edição local ativo", wrong_branch_init["result"]["instructions"])
            with self.assertRaisesRegex(ValueError, "somente na branch"):
                mcp_server._tool_result("edit_branch_file", {
                    "path": "lotomaster/script.py", "expected_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "content": "bad\n",
                }, transport="stdio")
        self.assertEqual(target.read_text(encoding="utf-8"), "before\n")

    def test_check_runner_uses_fixed_commands_and_sanitized_temporary_environment(self):
        calls = []

        def fake_check(label, command, env, timeout):
            calls.append((label, command, env, timeout))
            return {"check": label, "passed": True}

        with (
            patch.object(mcp_server, "_assert_branch_edit_access", return_value=mcp_server.EDITABLE_BRANCH),
            patch.object(mcp_server, "_working_tree_fingerprint", side_effect=["same", "same"]),
            patch.object(mcp_server, "_project_file_index", return_value=[]),
            patch.object(mcp_server, "_run_fixed_check", side_effect=fake_check),
            patch.object(mcp_server.shutil, "which", return_value="/usr/bin/node"),
            patch.dict(os.environ, {"OPENAI_API_KEY": "do-not-pass"}),
        ):
            result = mcp_server._run_branch_checks("stdio")
        self.assertTrue(result["all_passed"])
        labels = [item[0] for item in calls]
        self.assertEqual(labels, [
            "unittest_lotomaster", "node_check:lotomaster/static/app.js",
            "node_check:lotomaster/static/caixa-fallback.js", "git_diff_check",
        ])
        for _, command, env, _ in calls:
            self.assertNotIn("do-not-pass", env.values())
            self.assertNotIn("OPENAI_API_KEY", env)
        self.assertIn("lotomaster/tests", calls[0][1])
        self.assertEqual(calls[1][1][1:3], ["--check", "lotomaster/static/app.js"])


if __name__ == "__main__":
    unittest.main()
