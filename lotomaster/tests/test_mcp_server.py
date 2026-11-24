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
    def test_read_project_file_omits_digest_without_edit_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lotomaster").mkdir()
            (root / "lotomaster" / "script.py").write_text("safe\n", encoding="utf-8")
            with patch.object(mcp_server, "REPO_ROOT", root), patch.dict(
                os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "0"},
            ):
                stdio = mcp_server._tool_result(
                    "read_project_file", {"path": "lotomaster/script.py"}, transport="stdio",
                )
                http = mcp_server._tool_result(
                    "read_project_file", {"path": "lotomaster/script.py"}, transport="http",
                )
            self.assertNotIn("sha256", stdio)
            self.assertNotIn("sha256", http)

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
            (root / "secrets").mkdir()
            (root / "secrets" / "config.py").write_text("private = 'hidden'", encoding="utf-8")
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
                self.assertNotIn("sha256", read)
                self.assertNotIn("outside-link.py", paths)
                with self.assertRaisesRegex(ValueError, "fora do escopo"):
                    mcp_server._tool_result("read_project_file", {"path": "outside-link.py"})
                with self.assertRaisesRegex(ValueError, "não está no conjunto permitido"):
                    mcp_server._tool_result("read_project_file", {"path": ".env"})
                with self.assertRaisesRegex(ValueError, "não está no conjunto permitido"):
                    mcp_server._tool_result("read_project_file", {"path": "secrets/config.py"})
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

    def _bounded_fifo_child(self, root, script):
        project_root = Path(__file__).resolve().parents[2]
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(project_root),
            "PYTHONNOUSERSITE": "1",
        }
        return subprocess.run(
            [sys.executable, "-c", script, str(root)], cwd=project_root,
            env=environment, capture_output=True, text=True, timeout=2,
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
        temporary, root, _ = self._repo()
        self.addCleanup(temporary.cleanup)
        with patch.object(mcp_server, "REPO_ROOT", root), patch.dict(os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"}):
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
            read = mcp_server._dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "read_project_file", "arguments": {"path": "lotomaster/script.py"}},
            }, transport="stdio")["result"]["structuredContent"]
            result = mcp_server._dispatch({
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "edit_branch_file", "arguments": {
                    "path": "lotomaster/script.py", "expected_sha256": original_hash, "content": new_content,
                }},
            }, transport="stdio")["result"]["structuredContent"]
            review = mcp_server._tool_result("review_branch_diff", {}, transport="stdio")
            self.assertEqual(read["sha256"], original_hash)
        self.assertTrue(result["changed"])
        self.assertFalse(result["committed"])
        self.assertFalse(result["published"])
        self.assertEqual(result["previous_sha256"], original_hash)
        self.assertEqual(result["sha256"], hashlib.sha256(new_content.encode("utf-8")).hexdigest())
        self.assertIn("best-effort", result["concurrency_check"])
        self.assertEqual(target.read_text(encoding="utf-8"), new_content)
        self.assertEqual(list((root / "lotomaster").glob(".lotomaster-mcp-edit-*.tmp")), [])
        self.assertEqual(review["changed_files"], ["lotomaster/script.py"])
        self.assertIn("[REDACTED]", review["diff"])
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz0123456789", review["diff"])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO requer suporte POSIX")
    def test_edit_rejects_fifo_without_blocking(self):
        temporary, root, _ = self._repo()
        self.addCleanup(temporary.cleanup)
        fifo = root / "lotomaster" / "pipe.py"
        os.mkfifo(fifo)
        script = (
            "import os,sys\nfrom pathlib import Path\nfrom lotomaster import mcp_server\n"
            "mcp_server.REPO_ROOT=Path(sys.argv[1])\nos.environ['LOTOMASTER_MCP_ENABLE_BRANCH_EDIT']='1'\n"
            "try: mcp_server._tool_result('edit_branch_file', {'path':'lotomaster/pipe.py',"
            "'expected_sha256':'0000000000000000000000000000000000000000000000000000000000000000',"
            "'content':'safe\\n'}, transport='stdio')\n"
            "except ValueError as error: print(error)\n"
        )
        result = self._bounded_fifo_child(root, script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("arquivo regular", result.stdout)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO requer suporte POSIX")
    def test_edit_rejects_fifo_on_reopen_without_blocking(self):
        temporary, root, target = self._repo()
        self.addCleanup(temporary.cleanup)
        script = (
            "import os,sys; from pathlib import Path; from lotomaster import mcp_server; "
            "mcp_server.REPO_ROOT=Path(sys.argv[1]); os.environ['LOTOMASTER_MCP_ENABLE_BRANCH_EDIT']='1'; "
            "original_open=os.open; file_open_count=[0]; target=Path(sys.argv[1])/'lotomaster'/'script.py'\n"
            "def replacing_open(path, flags, *args, **kwargs):\n"
            "    if path=='script.py' and kwargs.get('dir_fd') is not None:\n"
            "        file_open_count[0]+=1\n"
            "        if file_open_count[0]==2: target.unlink(); os.mkfifo(target)\n"
            "    return original_open(path, flags, *args, **kwargs)\n"
            "os.open=replacing_open\n"
            "try: mcp_server._tool_result('edit_branch_file', {'path':'lotomaster/script.py',"
            "'expected_sha256':'" + hashlib.sha256(b"before\n").hexdigest() + "',"
            "'content':'safe\\n'}, transport='stdio')\n"
            "except ValueError as error: print(error)\n"
        )
        result = self._bounded_fifo_child(root, script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("tipo não permitido", result.stdout)
        self.assertTrue(target.exists())

    def test_review_separates_staged_and_unstaged_changes_and_keeps_safe_deletions(self):
        temporary, root, target = self._repo()
        self.addCleanup(temporary.cleanup)
        deleted = root / "lotomaster" / "deleted.py"
        deleted.write_text("tracked preimage\n", encoding="utf-8")
        self._git(root, "add", "lotomaster/deleted.py")
        self._git(root, "commit", "-q", "-m", "add deletable module")
        target.write_text("staged version\n", encoding="utf-8")
        self._git(root, "add", "lotomaster/script.py")
        target.write_text("working-tree version\n", encoding="utf-8")
        deleted.unlink()
        with patch.object(mcp_server, "REPO_ROOT", root), patch.dict(os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"}):
            review = mcp_server._tool_result("review_branch_diff", {}, transport="stdio")
        self.assertEqual(review["staged_files"], ["lotomaster/script.py"])
        self.assertEqual(review["changed_files"], ["lotomaster/deleted.py", "lotomaster/script.py"])
        self.assertIn("Staged changes:", review["diff"])
        self.assertIn("Unstaged changes:", review["diff"])
        self.assertIn("tracked preimage", review["diff"])
        self.assertIn("staged version", review["diff"])
        self.assertIn("working-tree version", review["diff"])

    def test_review_keeps_staged_addition_deleted_from_working_tree(self):
        temporary, root, _ = self._repo()
        self.addCleanup(temporary.cleanup)
        added = root / "lotomaster" / "added_then_deleted.py"
        added.write_text("staged addition\n", encoding="utf-8")
        self._git(root, "add", "lotomaster/added_then_deleted.py")
        added.unlink()
        with patch.object(mcp_server, "REPO_ROOT", root), patch.dict(
            os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"},
        ):
            review = mcp_server._tool_result("review_branch_diff", {}, transport="stdio")
        self.assertEqual(review["staged_files"], ["lotomaster/added_then_deleted.py"])
        self.assertEqual(review["changed_files"], ["lotomaster/added_then_deleted.py"])
        self.assertIn("staged addition", review["diff"])
        self.assertIn("Unstaged changes:", review["diff"])

    def test_review_disables_rename_detection_and_keeps_both_safe_paths(self):
        temporary, root, _ = self._repo()
        self.addCleanup(temporary.cleanup)
        old_path = root / "lotomaster" / "moved_old.py"
        old_path.write_text("rename contents\n", encoding="utf-8")
        self._git(root, "add", "lotomaster/moved_old.py")
        self._git(root, "commit", "-q", "-m", "add rename fixture")
        new_path = root / "lotomaster" / "moved_new.py"
        self._git(root, "mv", "lotomaster/moved_old.py", "lotomaster/moved_new.py")
        with patch.object(mcp_server, "REPO_ROOT", root), patch.dict(
            os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"},
        ):
            review = mcp_server._tool_result("review_branch_diff", {}, transport="stdio")
        self.assertEqual(review["changed_files"], ["lotomaster/moved_new.py", "lotomaster/moved_old.py"])
        self.assertIn("moved_new.py", review["diff"])
        self.assertIn("moved_old.py", review["diff"])
        self.assertTrue(new_path.exists())
        self.assertFalse(old_path.exists())

    def test_review_excludes_hidden_and_secret_paths_even_when_deleted(self):
        temporary, root, _ = self._repo()
        self.addCleanup(temporary.cleanup)
        hidden = root / "lotomaster" / ".private.py"
        secret = root / "lotomaster" / "secret_notes.py"
        hidden.write_text("hidden secret material\n", encoding="utf-8")
        secret.write_text("secret file material\n", encoding="utf-8")
        self._git(root, "add", "lotomaster/.private.py", "lotomaster/secret_notes.py")
        self._git(root, "commit", "-q", "-m", "add excluded path fixtures")
        hidden.unlink()
        secret.unlink()
        with patch.object(mcp_server, "REPO_ROOT", root), patch.dict(
            os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"},
        ):
            review = mcp_server._tool_result("review_branch_diff", {}, transport="stdio")
        self.assertEqual(review["changed_files"], [])
        self.assertNotIn("hidden secret material", review["diff"])
        self.assertNotIn("secret file material", review["diff"])

    def test_review_excludes_deleted_files_under_secret_directories(self):
        temporary, root, _ = self._repo()
        self.addCleanup(temporary.cleanup)
        secret_dir = root / "lotomaster" / "secrets"
        credential_dir = root / "lotomaster" / "credentials"
        secret_dir.mkdir()
        credential_dir.mkdir()
        staged_secret = secret_dir / "staged.py"
        unstaged_secret = credential_dir / "unstaged.py"
        staged_secret.write_text("staged secret contents\n", encoding="utf-8")
        unstaged_secret.write_text("unstaged credential contents\n", encoding="utf-8")
        self._git(root, "add", "lotomaster/secrets/staged.py", "lotomaster/credentials/unstaged.py")
        self._git(root, "commit", "-q", "-m", "add secret directory fixtures")
        staged_secret.unlink()
        self._git(root, "add", "-u", "lotomaster/secrets/staged.py")
        unstaged_secret.unlink()
        with patch.object(mcp_server, "REPO_ROOT", root), patch.dict(
            os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"},
        ):
            review = mcp_server._tool_result("review_branch_diff", {}, transport="stdio")
        self.assertNotIn("lotomaster/secrets/staged.py", review["changed_files"])
        self.assertNotIn("lotomaster/credentials/unstaged.py", review["changed_files"])
        self.assertNotIn("staged secret contents", review["diff"])
        self.assertNotIn("unstaged credential contents", review["diff"])

    def test_branch_checks_report_staged_and_unstaged_whitespace_independently(self):
        temporary, root, target = self._repo()
        self.addCleanup(temporary.cleanup)
        target.write_text("value = 1  \n", encoding="utf-8")
        self._git(root, "add", "lotomaster/script.py")
        self._git(root, "config", "core.whitespace", "blank-at-eol")
        target.write_text("value = 2  \n", encoding="utf-8")
        calls = []

        def run_check(label, command, env, timeout):
            calls.append((label, command, env, timeout))
            if label.startswith("git_diff_check_"):
                completed = subprocess.run(
                    command, cwd=root, env=env, capture_output=True, text=True, timeout=timeout,
                )
                return {
                    "check": label, "passed": completed.returncode == 0,
                    "output_excerpt": completed.stdout + completed.stderr,
                }
            return {"check": label, "passed": True}

        with (
            patch.object(mcp_server, "REPO_ROOT", root),
            patch.object(mcp_server, "_assert_branch_edit_access", return_value=mcp_server.EDITABLE_BRANCH),
            patch.object(mcp_server, "_run_fixed_check", side_effect=run_check),
            patch.object(mcp_server.shutil, "which", return_value="/usr/bin/node"),
        ):
            result = mcp_server._run_branch_checks("stdio")
        checks = {item["check"]: item for item in result["checks"]}
        labels = [item[0] for item in calls]
        self.assertIn("git_diff_check_staged", labels)
        self.assertIn("git_diff_check_unstaged", labels)
        self.assertFalse(checks["git_diff_check_staged"]["passed"])
        self.assertFalse(checks["git_diff_check_unstaged"]["passed"])
        for label, command, env, _ in calls:
            if label.startswith("git_diff_check_"):
                self.assertIn("core.whitespace=blank-at-eol", command)
                self.assertEqual(env["HOME"], os.path.dirname(env["LOTOMASTER_DB_PATH"]))

    def test_diff_redacts_a_complete_private_key_before_truncation(self):
        temporary, root, target = self._repo()
        self.addCleanup(temporary.cleanup)
        prefix = "diff --git a/lotomaster/script.py b/lotomaster/script.py\n" + ("context " * 14) + ("padding " * 4) + "\n"
        private_key = "-----BEGIN PRIVATE KEY-----\n" + ("SECRETKEYMATERIAL0123456789\n" * 30) + "-----END PRIVATE KEY-----\n"
        synthetic_diff = prefix + private_key + ("tail " * 100)

        def fake_git(arguments, *, timeout=10):
            if arguments == ["rev-parse", "--show-toplevel"]:
                return str(root) + "\n"
            if arguments == ["branch", "--show-current"]:
                return mcp_server.EDITABLE_BRANCH + "\n"
            if arguments[:2] == ["ls-tree", "-z"]:
                return ""
            if arguments[:2] == ["ls-files", "--stage"]:
                return ""
            if "--name-only" in arguments and "--cached" in arguments:
                return ""
            if "--name-only" in arguments:
                return "lotomaster/script.py\0"
            if "--no-ext-diff" in arguments:
                return synthetic_diff
            if arguments[:2] == ["ls-files", "--others"]:
                return ""
            raise AssertionError(arguments)

        with (
            patch.object(mcp_server, "REPO_ROOT", root),
            patch.object(mcp_server, "MAX_BRANCH_DIFF_BYTES", 256),
            patch.object(mcp_server, "_git_output", side_effect=fake_git),
            patch.object(mcp_server, "_capture_diff_source_versions", return_value=("a" * 40, {})),
            patch.dict(os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"}),
        ):
            review = mcp_server._tool_result("review_branch_diff", {}, transport="stdio")
        self.assertFalse(review["diff_complete"])
        self.assertTrue(review["secrets_redacted"])
        self.assertIn("[REDACTED PRIVATE KEY BLOCK]", review["diff"])
        self.assertNotIn("SECRETKEYMATERIAL", review["diff"])
        self.assertNotIn("-----BEGIN PRIVATE KEY-----", review["diff"])

    def test_real_staged_diff_redacts_private_key_using_complete_file_versions(self):
        temporary, root, target = self._repo()
        self.addCleanup(temporary.cleanup)
        body = [f"KEY{i:02d}abcdefghijklmnop" for i in range(12)]
        original = "prefix = True\n-----BEGIN PRIVATE KEY-----\n" + "\n".join(body) + "\n-----END PRIVATE KEY-----\n"
        target.write_text(original, encoding="utf-8")
        self._git(root, "add", "lotomaster/script.py")
        self._git(root, "commit", "-q", "-m", "store PEM fixture")
        changed = body.copy()
        changed[6] = "ALTKEY06abcdefghijklmnop"
        updated = "prefix = True\n-----BEGIN PRIVATE KEY-----\n" + "\n".join(changed) + "\n-----END PRIVATE KEY-----\n"
        target.write_text(updated, encoding="utf-8")
        self._git(root, "add", "lotomaster/script.py")
        with patch.object(mcp_server, "REPO_ROOT", root), patch.dict(
            os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"},
        ):
            review = mcp_server._tool_result("review_branch_diff", {}, transport="stdio")
        self.assertIn("[REDACTED PRIVATE KEY BLOCK]", review["diff"])
        self.assertNotIn(body[6], review["diff"])
        self.assertNotIn(changed[6], review["diff"])
        self.assertFalse(review["diff_withheld"])

    def test_review_withholds_diff_when_worktree_changes_during_render(self):
        temporary, root, target = self._repo()
        self.addCleanup(temporary.cleanup)
        target.write_text("rendered version\n", encoding="utf-8")
        original_git_output = mcp_server._git_output
        rendered = False

        def mutate_after_diff(arguments, *, timeout=10):
            nonlocal rendered
            output = original_git_output(arguments, timeout=timeout)
            if not rendered and arguments[:1] == ["diff"] and "--no-ext-diff" in arguments:
                target.write_text("raced version\n", encoding="utf-8")
                rendered = True
            return output

        with (
            patch.object(mcp_server, "REPO_ROOT", root),
            patch.object(mcp_server, "_git_output", side_effect=mutate_after_diff),
            patch.dict(os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"}),
        ):
            review = mcp_server._tool_result("review_branch_diff", {}, transport="stdio")
        self.assertTrue(rendered)
        self.assertTrue(review["diff_withheld"])
        self.assertFalse(review["diff_complete"])
        self.assertEqual(review["diff"], "")

    def test_review_withholds_diff_when_head_changes_during_render(self):
        temporary, root, target = self._repo()
        self.addCleanup(temporary.cleanup)
        target.write_text("unstaged change\n", encoding="utf-8")
        head = self._git(root, "rev-parse", "HEAD").stdout.strip()
        with (
            patch.object(mcp_server, "REPO_ROOT", root),
            patch.object(mcp_server, "_capture_diff_source_versions", side_effect=[(head, {}), ("0" * 40, {})]),
            patch.dict(os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"}),
        ):
            review = mcp_server._tool_result("review_branch_diff", {}, transport="stdio")
        self.assertTrue(review["diff_withheld"])
        self.assertFalse(review["diff_complete"])
        self.assertEqual(review["diff"], "")

    def test_fixed_check_bounds_output_redacts_retained_text_and_keeps_timeout(self):
        secret = "-----BEGIN PRIVATE KEY-----\nSECRETKEYMATERIAL0123456789\n-----END PRIVATE KEY-----"
        retained = mcp_server._run_fixed_check(
            "redaction", [sys.executable, "-c", "import sys;sys.stdout.write(sys.argv[1])", secret],
            os.environ.copy(), 5,
        )
        self.assertTrue(retained["passed"])
        self.assertNotIn("SECRETKEYMATERIAL", retained["output_excerpt"])
        self.assertIn("[REDACTED PRIVATE KEY BLOCK]", retained["output_excerpt"])
        with patch.object(mcp_server, "MAX_CHECK_CAPTURE_BYTES", 128):
            overflow = mcp_server._run_fixed_check(
                "overflow", [sys.executable, "-c", "print('S' * 10000)"], os.environ.copy(), 5,
            )
        self.assertFalse(overflow["passed"])
        self.assertTrue(overflow["output_limit_exceeded"])
        self.assertNotIn("S" * 80, overflow["output_excerpt"])
        timed_out = mcp_server._run_fixed_check(
            "timeout", [sys.executable, "-c", "import time;time.sleep(10)"], os.environ.copy(), 0.01,
        )
        self.assertTrue(timed_out["timed_out"])

    @unittest.skipUnless(os.name == "posix", "encerramento de grupo de processos requer POSIX")
    def test_fixed_check_timeout_kills_ready_descendants_holding_pipes(self):
        with tempfile.TemporaryDirectory() as directory:
            ready = Path(directory) / "descendant-ready.txt"
            marker = Path(directory) / "descendant-survived.txt"
            child_script = (
                "import pathlib,sys,time;pathlib.Path(sys.argv[1]).write_text('ready');"
                "time.sleep(4);pathlib.Path(sys.argv[2]).write_text('alive')"
            )
            parent_script = (
                "import pathlib,subprocess,sys,time\n"
                "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2],sys.argv[3]])\n"
                "deadline=time.monotonic()+2\n"
                "while not pathlib.Path(sys.argv[2]).exists() and time.monotonic()<deadline:\n"
                "    time.sleep(.01)\n"
                "if not pathlib.Path(sys.argv[2]).exists():\n"
                "    raise SystemExit(3)\n"
                "time.sleep(10)"
            )
            result = mcp_server._run_fixed_check(
                "descendant-timeout", [sys.executable, "-c", parent_script, child_script, str(ready), str(marker)],
                os.environ.copy(), 3,
            )
            self.assertTrue(result["timed_out"])
            self.assertTrue(ready.exists(), "the child must signal readiness before the timeout")
            threading.Event().wait(1.2)
            self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == "posix", "encerramento de grupo de processos requer POSIX")
    def test_fixed_check_marks_forced_cleanup_incomplete_when_leader_exits_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            ready = Path(directory) / "descendant-ready.txt"
            marker = Path(directory) / "descendant-survived.txt"
            child_script = (
                "import pathlib,sys,time;pathlib.Path(sys.argv[1]).write_text('ready');"
                "time.sleep(5);pathlib.Path(sys.argv[2]).write_text('alive')"
            )
            parent_script = (
                "import pathlib,subprocess,sys,time\n"
                "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2],sys.argv[3]])\n"
                "deadline=time.monotonic()+2\n"
                "while not pathlib.Path(sys.argv[2]).exists() and time.monotonic()<deadline:\n"
                "    time.sleep(.01)\n"
                "if not pathlib.Path(sys.argv[2]).exists():\n"
                "    raise SystemExit(3)\n"
                "raise SystemExit(0)"
            )
            result = mcp_server._run_fixed_check(
                "descendant-incomplete",
                [sys.executable, "-c", parent_script, child_script, str(ready), str(marker)],
                os.environ.copy(), 5,
            )
            self.assertTrue(ready.exists(), "the child must signal readiness before the leader exits")
            self.assertFalse(result["passed"])
            self.assertFalse(result.get("timed_out", False))
            self.assertTrue(result["incomplete"])
            threading.Event().wait(5.2)
            self.assertFalse(marker.exists())

    def test_fingerprint_covers_repository_wide_and_staged_content(self):
        temporary, root, target = self._repo()
        self.addCleanup(temporary.cleanup)
        outside = root / "tracked.py"
        outside.write_text("original\n", encoding="utf-8")
        self._git(root, "add", "tracked.py")
        self._git(root, "commit", "-q", "-m", "add outside tracked file")
        with patch.object(mcp_server, "REPO_ROOT", root):
            clean = mcp_server._working_tree_fingerprint()
            outside.write_text("changed outside lotomaster\n", encoding="utf-8")
            outside_changed = mcp_server._working_tree_fingerprint()
            self.assertNotEqual(clean, outside_changed)
            outside.write_text("original\n", encoding="utf-8")

            untracked = root / "outside_untracked.py"
            untracked.write_text("first untracked content\n", encoding="utf-8")
            untracked_first = mcp_server._working_tree_fingerprint()
            untracked.write_text("second untracked content\n", encoding="utf-8")
            untracked_second = mcp_server._working_tree_fingerprint()
            self.assertNotEqual(untracked_first, untracked_second)
            untracked.unlink()

            before_head_change = mcp_server._working_tree_fingerprint()
            self._git(root, "commit", "--allow-empty", "-q", "-m", "advance HEAD without tree changes")
            after_head_change = mcp_server._working_tree_fingerprint()
            self.assertNotEqual(before_head_change, after_head_change)

            target.write_text("first staged content\n", encoding="utf-8")
            self._git(root, "add", "lotomaster/script.py")
            target.write_text("before\n", encoding="utf-8")
            staged_first = mcp_server._working_tree_fingerprint()
            target.write_text("second staged content\n", encoding="utf-8")
            self._git(root, "add", "lotomaster/script.py")
            target.write_text("before\n", encoding="utf-8")
            staged_second = mcp_server._working_tree_fingerprint()
        self.assertNotEqual(staged_first, staged_second)

    @unittest.skipUnless(os.name == "posix", "teste de grupo de processos requer POSIX")
    def test_git_fingerprint_rejects_forced_process_group_cleanup_after_zero_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            marker = root / "child-survived.txt"
            fake_git = fake_bin / "git"
            child_script = (
                "import pathlib,sys,time;time.sleep(2);"
                "pathlib.Path(sys.argv[1]).write_text('alive')"
            )
            fake_git.write_text(
                "#!/usr/bin/env python3\n"
                "import subprocess,sys\n"
                f"subprocess.Popen([sys.executable,'-c',{child_script!r},{str(marker)!r}])\n"
                "sys.stdout.buffer.write(b'partial fingerprint')\n"
                "sys.stdout.flush()\n",
                encoding="utf-8",
            )
            fake_git.chmod(0o755)
            with (
                patch.object(mcp_server, "REPO_ROOT", root),
                patch.dict(os.environ, {"PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", "")}),
            ):
                with self.assertRaisesRegex(ValueError, "interrompida"):
                    mcp_server._git_stream_fingerprint(["diff"], max_bytes=1024, timeout=5)
            threading.Event().wait(2.2)
            self.assertFalse(marker.exists())

    def test_fallback_snapshot_reads_at_most_limit_plus_one(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "file.py"
            target.write_bytes(b"12345678")
            with patch.object(mcp_server, "MAX_PROJECT_FILE_BYTES", 8):
                _, snapshot = mcp_server._safe_worktree_snapshot_fallback(target)
            self.assertEqual(snapshot, b"12345678")

            target.write_bytes(b"12345678")
            original_read = mcp_server._read_fd_limited
            bytes_read = []

            def grow_then_read(file_fd, limit):
                with target.open("ab") as writer:
                    writer.write(b"x" * 100_000)
                content = original_read(file_fd, limit)
                bytes_read.append(len(content))
                return content

            with (
                patch.object(mcp_server, "MAX_PROJECT_FILE_BYTES", 8),
                patch.object(mcp_server, "_read_fd_limited", side_effect=grow_then_read),
            ):
                with self.assertRaisesRegex(ValueError, "mudou durante a revisão"):
                    mcp_server._safe_worktree_snapshot_fallback(target)
            self.assertEqual(bytes_read, [9])

    def test_review_withholds_diff_for_unverified_git_worktree_encoding(self):
        temporary, root, target = self._repo()
        self.addCleanup(temporary.cleanup)
        body = [f"SECRETKEY{i:02d}abcdefghijklmnop" for i in range(12)]
        original = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(body) + "\n-----END PRIVATE KEY-----\n"
        target.write_text(original, encoding="utf-8")
        self._git(root, "add", "lotomaster/script.py")
        self._git(root, "commit", "-q", "-m", "store UTF-8 PEM fixture")

        attributes_file = root / ".gitattributes"
        attributes_file.write_text("lotomaster/*.py working-tree-encoding=UTF-16LE\n", encoding="utf-8")
        self._git(root, "add", ".gitattributes")
        self._git(root, "commit", "-q", "-m", "configure working-tree encoding")
        target.unlink()
        self._git(root, "checkout", "--", "lotomaster/script.py")
        changed = body.copy()
        changed[6] = "ALTERNATEKEY06abcdefghijklmnop"
        updated = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(changed) + "\n-----END PRIVATE KEY-----\n"
        target.write_bytes(updated.encode("utf-16le"))
        git_diff = self._git(root, "diff", "--", "lotomaster/script.py").stdout
        self.assertIn(changed[6], git_diff)

        with patch.object(mcp_server, "REPO_ROOT", root), patch.dict(
            os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"},
        ):
            self.assertEqual(
                mcp_server._git_path_attributes("lotomaster/script.py")["working-tree-encoding"],
                "UTF-16LE",
            )
            review = mcp_server._tool_result("review_branch_diff", {}, transport="stdio")
        self.assertTrue(review["diff_withheld"])
        self.assertEqual(review["diff"], "")
        self.assertNotIn(changed[6], review["diff"])

    def test_review_withholds_diff_for_git_clean_filter(self):
        temporary, root, target = self._repo()
        self.addCleanup(temporary.cleanup)
        target.write_text("changed content\n", encoding="utf-8")
        attributes_file = root / ".gitattributes"
        attributes_file.write_text("lotomaster/*.py filter=unverified\n", encoding="utf-8")
        self._git(root, "add", ".gitattributes")
        self._git(root, "commit", "-q", "-m", "configure custom clean filter")

        with patch.object(mcp_server, "REPO_ROOT", root), patch.dict(
            os.environ, {"LOTOMASTER_MCP_ENABLE_BRANCH_EDIT": "1"},
        ):
            self.assertEqual(mcp_server._git_path_attributes("lotomaster/script.py")["filter"], "unverified")
            review = mcp_server._tool_result("review_branch_diff", {}, transport="stdio")
        self.assertTrue(review["diff_withheld"])
        self.assertEqual(review["diff"], "")

    def test_fingerprint_rejects_git_diff_larger_than_capture_limit(self):
        temporary, root, target = self._repo()
        self.addCleanup(temporary.cleanup)
        target.write_text("value = '" + ("x" * 500) + "'\n", encoding="utf-8")
        with (
            patch.object(mcp_server, "REPO_ROOT", root),
            patch.object(mcp_server, "MAX_FINGERPRINT_DIFF_BYTES", 128),
        ):
            with self.assertRaisesRegex(ValueError, "excede o limite do fingerprint"):
                mcp_server._working_tree_fingerprint()

    def test_untracked_fingerprint_consumes_aggregate_budget_by_actual_reads(self):
        temporary, root, _ = self._repo()
        self.addCleanup(temporary.cleanup)
        (root / "a.py").write_text("123456", encoding="utf-8")
        (root / "b.py").write_text("abcdef", encoding="utf-8")
        with (
            patch.object(mcp_server, "REPO_ROOT", root),
            patch.object(mcp_server, "MAX_UNTRACKED_FINGERPRINT_BYTES", 10),
        ):
            with self.assertRaisesRegex(ValueError, "fora dos limites de verificação segura"):
                mcp_server._working_tree_fingerprint()

    def test_check_runner_reports_tracked_changes_outside_lotomaster(self):
        temporary, root, _ = self._repo()
        self.addCleanup(temporary.cleanup)
        outside = root / "tracked.py"
        outside.write_text("before\n", encoding="utf-8")
        self._git(root, "add", "tracked.py")
        self._git(root, "commit", "-q", "-m", "add outside tracked file")
        changed = []

        def fake_check(label, command, env, timeout):
            if not changed:
                outside.write_text("modified by check\n", encoding="utf-8")
                changed.append(True)
            return {"check": label, "passed": True}

        with (
            patch.object(mcp_server, "REPO_ROOT", root),
            patch.object(mcp_server, "_assert_branch_edit_access", return_value=mcp_server.EDITABLE_BRANCH),
            patch.object(mcp_server, "_run_fixed_check", side_effect=fake_check),
            patch.object(mcp_server.shutil, "which", return_value="/usr/bin/node"),
        ):
            result = mcp_server._run_branch_checks("stdio")
        self.assertFalse(result["working_tree_unchanged"])
        self.assertFalse(result["all_passed"])

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
            "node_check:lotomaster/static/caixa-fallback.js",
            "git_diff_check_staged", "git_diff_check_unstaged",
        ])
        for _, command, env, _ in calls:
            self.assertNotIn("do-not-pass", env.values())
            self.assertNotIn("OPENAI_API_KEY", env)
        self.assertIn("lotomaster/tests", calls[0][1])
        self.assertEqual(calls[1][1][1:3], ["--check", "lotomaster/static/app.js"])
        self.assertIn("--cached", calls[-2][1])
        self.assertNotIn("--cached", calls[-1][1])
        for _, command, _, _ in calls[-2:]:
            self.assertIn("core.whitespace=blank-at-eol", command)


if __name__ == "__main__":
    unittest.main()
