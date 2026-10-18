import hashlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

CHAIN_FILE = Path(__file__).with_name("wtp_blockchain.json")
HOST = "0.0.0.0"
PORT = 8767


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def make_hash(block):
    contents = {
        key: value
        for key, value in block.items()
        if key != "hash"
    }
    return hashlib.sha256(
        canonical(contents).encode("utf-8")
    ).hexdigest()


def read_chain_status():
    with CHAIN_FILE.open("r", encoding="utf-8") as file:
        chain = json.load(file)

    if not isinstance(chain, list) or not chain:
        raise ValueError("Blockchain must be a non-empty list.")

    for i, block in enumerate(chain):
        if not isinstance(block, dict):
            raise ValueError(f"Invalid block at position {i}.")

        required = {
            "number", "time", "miner", "reward",
            "previous_hash", "nonce", "transactions", "hash"
        }

        if set(block) != required:
            raise ValueError(f"Unexpected fields in block {i}.")

        if block["hash"] != make_hash(block):
            raise ValueError(f"Hash mismatch at block {i}.")

        if i == 0:
            if block["number"] != 1 or block["previous_hash"] != "0":
                raise ValueError("Unexpected genesis block.")
        else:
            previous = chain[i - 1]
            if block["number"] != previous["number"] + 1:
                raise ValueError("Block numbering mismatch.")
            if block["previous_hash"] != previous["hash"]:
                raise ValueError("Previous-hash link mismatch.")

    latest = chain[-1]

    return {
        "project": "We The People Coin",
        "read_only": True,
        "block_count": len(chain),
        "latest_block": latest["number"],
        "latest_hash": latest["hash"],
        "total_mining_rewards": sum(
            block["reward"] for block in chain
        ),
        "note": "Basic block hashes and links checked only. "
                "Transactions and signatures are not fully validated."
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import unquote, urlsplit
        path = "".join(
            c for c in unquote(urlsplit(self.path).path)
            if c.isascii() and (c.isalnum() or c in "/_-")
        )
        try:
            if path == "/api/status":
                result = read_chain_status()

            elif path == "/api/blocks":
                read_chain_status()
                with CHAIN_FILE.open("r", encoding="utf-8") as file:
                    chain = json.load(file)

                result = {
                    "blocks": [
                        {
                            "number": block["number"],
                            "time": block["time"],
                            "reward": block["reward"],
                            "previous_hash": block["previous_hash"],
                            "hash": block["hash"],
                            "nonce": block["nonce"],
                            "transaction_count": len(block["transactions"])
                        }
                        for block in chain[-50:]
                    ]
                }

            elif path.startswith("/api/block/"):
                number_text = path.rsplit("/", 1)[-1]

                if not number_text.isdigit():
                    self.send_error(400, "Invalid block number")
                    return

                read_chain_status()
                with CHAIN_FILE.open("r", encoding="utf-8") as file:
                    chain = json.load(file)

                number = int(number_text)
                block = next(
                    (item for item in chain if item["number"] == number),
                    None
                )

                if block is None:
                    self.send_error(404, "Block not found")
                    return

                result = {
                    "block": {
                        "number": block["number"],
                        "time": block["time"],
                        "reward": block["reward"],
                        "previous_hash": block["previous_hash"],
                        "hash": block["hash"],
                        "nonce": block["nonce"],
                        "transaction_count": len(block["transactions"])
                    }
                }

            else:
                self.send_error(404, "Unknown API endpoint")
                return

            body = json.dumps(result, indent=2).encode("utf-8")
            status = 200

        except Exception as error:
            body = json.dumps({"error": str(error)}).encode("utf-8")
            status = 500


        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print("API:", format % args)


if __name__ == "__main__":
    print("WTP read-only API")
    print("Local address: http://127.0.0.1:8765/api/status")
    print("Only this computer can connect.")
    print("Press Ctrl+C to stop.")

    server = HTTPServer((HOST, PORT), Handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nRead-only API stopped.")
    finally:
        server.server_close()