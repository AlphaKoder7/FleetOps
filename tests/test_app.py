import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "server", Path(__file__).resolve().parents[1] / "app/server.py"
)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class ConfigTests(unittest.TestCase):
    def test_valid_config_and_invalid_ready_are_distinguished(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            config = dict(
                node="fleetops-web-1",
                version="1.0.0",
                ready=True,
                bind="127.0.0.1",
                port=18081,
            )
            path.write_text(json.dumps(config))
            self.assertEqual(server.load_config(path), config)
            config["ready"] = "yes"
            path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                server.load_config(path)


class EndpointTests(unittest.TestCase):
    def request(self, ready, path):
        from io import BytesIO
        from unittest.mock import patch

        config = dict(
            node="fleetops-web-1",
            version="1.0.0",
            ready=ready,
            bind="127.0.0.1",
            port=18081,
        )
        with patch.object(
            server, "ThreadingHTTPServer", side_effect=lambda address, handler: handler
        ):
            handler_class = server.make_server(config)
        handler = object.__new__(handler_class)
        handler.path = path
        handler.wfile = BytesIO()
        result = {"headers": {}}
        handler.send_response = lambda status: result.update(status=status)
        handler.send_header = lambda key, value: result["headers"].update({key: value})
        handler.end_headers = lambda: None
        handler.do_GET()
        result["body"] = json.loads(handler.wfile.getvalue())
        return result

    def test_ready_health_and_identity(self):
        for path in ["/", "/health"]:
            response = self.request(True, path)
            self.assertEqual(response["status"], 200)
            self.assertEqual(response["body"]["node"], "fleetops-web-1")
            self.assertEqual(response["headers"]["Content-Type"], "application/json")

    def test_not_ready_is_503_and_unknown_path_is_404(self):
        self.assertEqual(self.request(False, "/health")["status"], 503)
        self.assertEqual(self.request(True, "/missing")["status"], 404)
