from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os

HOST = "0.0.0.0"
PORT = 8765
CHAIN_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "wtp_blockchain.json"
)


class WTPStatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/status":
            self.send_error(404, "Not found")
            return

        try:
            with open(CHAIN_FILE, "r", encoding="utf-8") as file:
                chain = json.load(file)

            if not isinstance(chain, list) or not chain:
                raise ValueError("Blockchain is empty or invalid")

            response = {
                "name": "WTP Coin",
                "node_status": "online",
                "blocks": len(chain),
                "latest_block": chain[-1].get("number"),
                "latest_hash": chain[-1].get("hash"),
                "networking": "Peer synchronization not enabled yet"
            }
            status_code = 200

        except (OSError, ValueError, json.JSONDecodeError) as error:
            response = {
                "name": "WTP Coin",
                "node_status": "error",
                "message": str(error)
            }
            status_code = 500

        body = json.dumps(response, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"{self.client_address[0]} - {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), WTPStatusHandler)
    print("WTP Coin read-only status server is running.")
    print("Phone URL: http://192.168.1.240:8765/status")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()