import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8769


class MiningHandler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/status":
            self.send_json(404, {"error": "Not found"})
            return

        try:
            import wtp_coin

            chain = wtp_coin.load_chain()
            valid = wtp_coin.validate_chain(chain)

            self.send_json(200, {
                "coin": "WTP Coin",
                "service": "Mining API",
                "status": "online",
                "block_count": len(chain),
                "chain_valid": valid,
                "mining": "External mining not enabled yet",
                "next_step": "Implement verified work and block submission"
            })
        except Exception:
            self.send_json(500, {"error": "Could not read blockchain"})

    def do_POST(self):
        self.send_json(403, {
            "error": "Block submission is disabled until consensus validation is implemented"
        })

    def log_message(self, fmt, *args):
        print(fmt % args)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), MiningHandler)
    print("WTP Coin mining API started.")
    print("Local test: http://127.0.0.1:8769/status")
    print("Bound to this computer only; external miners are not enabled.")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nMining API stopped.")
    finally:
        server.server_close()