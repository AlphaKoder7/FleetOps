"""Dependency-free, validated FleetOps demonstration workload."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path


def load_config(path):
    config = json.loads(Path(path).read_text())
    required = {"node", "version", "ready", "bind", "port"}
    if set(config) != required or not isinstance(config["ready"], bool):
        raise ValueError("Expected node/version/ready/bind/port; ready must be boolean")
    if not all(isinstance(config[key], str) and config[key] for key in ("node", "version", "bind")):
        raise ValueError("node, version and bind must be nonempty strings")
    if type(config["port"]) is not int or config["port"] != 18081:
        raise ValueError("Lab application port must be 18081")
    return config


def make_server(config, address=None):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/", "/health"):
                status, body = 404, {"error": "not found"}
            else:
                status = 200 if config["ready"] else 503
                body = {"node": config["node"], "version": config["version"], "ready": config["ready"]}
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return ThreadingHTTPServer(address or (config["bind"], config["port"]), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/etc/fleetops/application.json")
    parser.add_argument("--validate")
    args = parser.parse_args()
    config = load_config(args.validate or args.config)
    if not args.validate:
        with make_server(config) as server:
            server.serve_forever()


if __name__ == "__main__":
    main()
