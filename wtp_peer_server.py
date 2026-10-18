from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import json
import os

HOST = "0.0.0.0"
PORT = 8766
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHAIN_FILE = os.path.join(BASE_DIR, "wtp_blockchain.json")
MAX_BLOCKS_PER_REQUEST = 100
MAX_ALLOWED_LIMIT = 100

NETWORK_NAME = "WTP Coin"
GENESIS_HASH = (
    "0000018895ebfbc03bec183f2d6c1da0b07bba1ff1c6a73b3fe5d2f6ab2db440"
)


class WTPPeerHandler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        body = json.dumps(data, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_chain(self):
        with open(CHAIN_FILE, "r", encoding="utf-8") as file:
            chain = json.load(file)

        if not isinstance(chain, list) or not chain:
            raise ValueError("Blockchain is empty or invalid.")

        if not isinstance(chain[0], dict):
            raise ValueError("Genesis block is invalid.")

        if chain[0].get("hash") != GENESIS_HASH:
            raise ValueError("Genesis hash does not match WTP Coin.")

        return chain

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/peer/info":
            try:
                chain = self.read_chain()
                self.send_json({
                    "name": NETWORK_NAME,
                    "genesis_hash": chain[0]["hash"],
                    "protocol_version": 2,
                    "blocks_available": len(chain),
                    "latest_block": chain[-1].get("number"),
                    "latest_hash": chain[-1].get("hash"),
                    "pagination": True,
                    "full_chain_validation": False
                })
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 500)
            return

        if parsed.path != "/peer/blocks":
            self.send_error(404, "Not found")
            return

        try:
            chain = self.read_chain()
            params = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}

            if "start" in params:
                start = int(params["start"][0])
                limit = int(params.get("limit", ["100"])[0])
            else:
                # Preserve old behavior when no pagination is requested.
                limit = int(params.get("limit", ["100"])[0])
                start = max(0, len(chain) - limit)

            if start < 0:
                raise ValueError("'start' must be zero or greater.")

            if limit < 1 or limit > MAX_ALLOWED_LIMIT:
                raise ValueError("'limit' must be between 1 and 100.")

            blocks = chain[start:start + limit]
            next_start = start + len(blocks)
            if next_start >= len(chain):
                next_start = None

            self.send_json({
                "name": NETWORK_NAME,
                "protocol_version": 2,
                "blocks_available": len(chain),
                "start": start,
                "returned_blocks": len(blocks),
                "next_start": next_start,
                "latest_block": chain[-1].get("number"),
                "latest_hash": chain[-1].get("hash"),
                "blocks": blocks,
                "notice": (
                    "Read-only block data. This endpoint checks the genesis "
                    "identity but does not validate the complete chain. "
                    "A receiving node must independently validate all blocks."
                )
            })

        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)

    def log_message(self, format, *args):
        print(f"{self.client_address[0]} - {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), WTPPeerHandler)
    print("WTP Coin paginated peer-data server started on port 8766.")
    print("Network identity: /peer/info")
    print("Latest blocks: /peer/blocks")
    print("Page example: /peer/blocks?start=0&limit=100")
    print("Read-only data only; synchronization is not enabled.")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPeer-data server stopped.")
    finally:
        server.server_close()
