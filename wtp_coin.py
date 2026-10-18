import hashlib
import json
import os
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

MAX_SUPPLY = 21_000_000
BLOCK_REWARD = 50
HALVING_INTERVAL = 210_000
DIFFICULTY = 4
TARGET_BLOCK_SECONDS = 60
DIFFICULTY_ADJUSTMENT_INTERVAL = 10
MAX_DIFFICULTY = 6
DIFFICULTY_ACTIVATION_BLOCK = 23500


def reward_for_block(block_number):
    halvings = block_number // HALVING_INTERVAL
    reward = BLOCK_REWARD

    for _ in range(halvings):
        reward = max(1, reward // 2)

    return reward


def difficulty_for_next_block(chain):
    if not chain:
        return DIFFICULTY

    next_number = chain[-1]["number"] + 1
    activation = DIFFICULTY_ACTIVATION_BLOCK
    interval = DIFFICULTY_ADJUSTMENT_INTERVAL

    if next_number < activation:
        return DIFFICULTY

    current_difficulty = DIFFICULTY

    for adjustment_block in range(
        activation, next_number + 1, interval
    ):
        first_number = adjustment_block - interval
        last_number = adjustment_block - 1

        timestamps = {
            block["number"]: block["time"]
            for block in chain
            if first_number <= block["number"] <= last_number
        }

        if len(timestamps) != interval:
            break

        try:
            first_time = datetime.fromisoformat(
                timestamps[first_number]
            )
            last_time = datetime.fromisoformat(
                timestamps[last_number]
            )
        except (ValueError, TypeError):
            break

        elapsed = (last_time - first_time).total_seconds()
        target = TARGET_BLOCK_SECONDS * (interval - 1)

        if elapsed < target / 2:
            current_difficulty = min(
                current_difficulty + 1,
                MAX_DIFFICULTY
            )
        elif elapsed > target * 2:
            current_difficulty = max(
                current_difficulty - 1,
                1
            )

    return current_difficulty


CHAIN_FILE = "wtp_blockchain.json"
KEY_FILE = "wtp_private_key.pem"
PENDING_FILE = "wtp_pending_transactions.json"


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def make_hash(block):
    contents = {
        key: value
        for key, value in block.items()
        if key != "hash"
    }
    return hashlib.sha256(canonical(contents).encode()).hexdigest()


def load_wallet():
    if not os.path.exists(KEY_FILE):
        raise FileNotFoundError(
            "Wallet key not found. Keep your existing "
            "wtp_private_key.pem file in this folder."
        )

    with open(KEY_FILE, "rb") as file:
        private_key = serialization.load_pem_private_key(
            file.read(), password=None
        )

    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    address = hashlib.sha256(public_bytes).hexdigest()
    return private_key, public_bytes, address


def load_public_key(public_hex):
    return serialization.load_der_public_key(bytes.fromhex(public_hex))


def transaction_message(tx):
    return canonical({
        "sender": tx["sender"],
        "recipient": tx["recipient"],
        "amount": tx["amount"]
    }).encode()


def verify_transaction(tx):
    try:
        required = {
            "sender", "recipient", "amount",
            "public_key", "signature"
        }

        if not isinstance(tx, dict) or set(tx) != required:
            return False

        amount = tx["amount"]

        if type(amount) is not int or amount <= 0:
            return False

        if not isinstance(tx["sender"], str) or not tx["sender"]:
            return False

        if not isinstance(tx["recipient"], str) or not tx["recipient"]:
            return False

        if not isinstance(tx["public_key"], str):
            return False

        if not isinstance(tx["signature"], str):
            return False

        public_bytes = bytes.fromhex(tx["public_key"])
        sender_address = hashlib.sha256(public_bytes).hexdigest()

        if sender_address != tx["sender"]:
            return False

        public_key = load_public_key(tx["public_key"])
        signature = bytes.fromhex(tx["signature"])

        public_key.verify(
            signature,
            transaction_message(tx),
            ec.ECDSA(hashes.SHA256())
        )

        return True

    except (
        InvalidSignature,
        ValueError,
        TypeError,
        KeyError,
        AttributeError
    ):
        return False


def balances_for(chain):
    balances = {}

    for block in chain:
        # Transactions happen before the block reward is credited.
        for tx in block.get("transactions", []):
            sender = tx["sender"]
            recipient = tx["recipient"]
            amount = tx["amount"]

            balances[sender] = balances.get(sender, 0) - amount
            balances[recipient] = balances.get(recipient, 0) + amount

        miner = block["miner"]
        balances[miner] = balances.get(miner, 0) + block["reward"]

    return balances


def validate_chain(chain):
    if not isinstance(chain, list) or not chain:
        return False

    balances = {}
    total_rewards = 0
    current_difficulty = DIFFICULTY

    required_fields = {
        "number", "time", "miner", "reward",
        "previous_hash", "nonce", "transactions", "hash"
    }

    for index, block in enumerate(chain):
        if not isinstance(block, dict):
            return False

        if set(block) != required_fields:
            return False

        if type(block["number"]) is not int or block["number"] < 1:
            return False

        if type(block["reward"]) is not int or block["reward"] < 0:
            return False

        if type(block["nonce"]) is not int or block["nonce"] < 0:
            return False

        if not isinstance(block["miner"], str) or not block["miner"]:
            return False

        if not isinstance(block["time"], str):
            return False

        if not isinstance(block["previous_hash"], str):
            return False

        if not isinstance(block["hash"], str):
            return False

        if not isinstance(block["transactions"], list):
            return False

        if block["hash"] != make_hash(block):
            return False

        expected_difficulty = DIFFICULTY

        if block["number"] >= DIFFICULTY_ACTIVATION_BLOCK:
            interval = DIFFICULTY_ADJUSTMENT_INTERVAL

            if (
                block["number"] - DIFFICULTY_ACTIVATION_BLOCK
            ) % interval == 0:
                first_number = block["number"] - interval
                last_number = block["number"] - 1

                timestamps = {
                    item["number"]: item["time"]
                    for item in chain[:index]
                    if first_number <= item["number"] <= last_number
                }

                if len(timestamps) != interval:
                    return False

                try:
                    first_time = datetime.fromisoformat(
                        timestamps[first_number]
                    )
                    last_time = datetime.fromisoformat(
                        timestamps[last_number]
                    )
                except (ValueError, TypeError):
                    return False

                elapsed = (last_time - first_time).total_seconds()
                target = TARGET_BLOCK_SECONDS * (interval - 1)

                if elapsed < target / 2:
                    current_difficulty = min(
                        current_difficulty + 1,
                        MAX_DIFFICULTY
                    )
                elif elapsed > target * 2:
                    current_difficulty = max(
                        current_difficulty - 1,
                        1
                    )

            expected_difficulty = current_difficulty

        if not block["hash"].startswith("0" * expected_difficulty):
            return False

        if index == 0:
            if block["number"] != 1:
                return False

            if block["previous_hash"] != "0":
                return False

            if block["reward"] != 0:
                return False

        else:
            previous = chain[index - 1]

            if block["number"] != previous["number"] + 1:
                return False

            if block["previous_hash"] != previous["hash"]:
                return False

            expected_reward = min(
                reward_for_block(block["number"]),
                MAX_SUPPLY - total_rewards
            )

            if block["reward"] != expected_reward:
                return False

        # Verify transactions and prevent spending money
        # that the sender does not have.
        for tx in block["transactions"]:
            if not verify_transaction(tx):
                return False

            sender = tx["sender"]
            recipient = tx["recipient"]
            amount = tx["amount"]

            if balances.get(sender, 0) < amount:
                return False

            balances[sender] = balances.get(sender, 0) - amount
            balances[recipient] = balances.get(recipient, 0) + amount

        # Credit the miner only after checking transactions.
        miner = block["miner"]
        balances[miner] = balances.get(miner, 0) + block["reward"]

        total_rewards += block["reward"]

        if total_rewards > MAX_SUPPLY:
            return False

    return True


def mine_block(number, miner, reward, previous_hash, transactions, difficulty=None):
    block = {
        "number": number,
        "time": datetime.now().isoformat(),
        "miner": miner,
        "reward": reward,
        "previous_hash": previous_hash,
        "nonce": 0,
        "transactions": transactions
    }

    if difficulty is None:
        difficulty = DIFFICULTY

    target = "0" * difficulty

    while True:
        block_hash = make_hash(block)

        if block_hash.startswith(target):
            block["hash"] = block_hash
            return block

        block["nonce"] += 1


def save_chain(chain):
    temp_file = CHAIN_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(chain, file, indent=2)

    os.replace(temp_file, CHAIN_FILE)


def migrate_old_chain(chain):
    print("Migrating your old WTP blockchain...")

    # Work on copies so the loaded chain isn't partially modified.
    migrated = []

    for index, old_block in enumerate(chain):
        block = dict(old_block)
        block["transactions"] = []

        if index == 0:
            block["previous_hash"] = "0"
        else:
            block["previous_hash"] = migrated[index - 1]["hash"]

        block["nonce"] = 0
        block.pop("hash", None)

        while True:
            block_hash = make_hash(block)

            if block_hash.startswith("0" * DIFFICULTY):
                block["hash"] = block_hash
                break

            block["nonce"] += 1

        migrated.append(block)

    if not validate_chain(migrated):
        raise ValueError(
            "Migration validation failed. Your original backup "
            "has not been changed. Stop and check the backup."
        )

    save_chain(migrated)
    print("Old blocks migrated successfully.")
    return migrated


def load_chain():
    if os.path.exists(CHAIN_FILE):
        with open(CHAIN_FILE, "r", encoding="utf-8") as file:
            chain = json.load(file)

        if not isinstance(chain, list) or not chain:
            raise ValueError("Saved blockchain is empty or invalid.")

        # Migrate only a completely old-format chain.
        if all(
            isinstance(block, dict) and "transactions" not in block
            for block in chain
        ):
            chain = migrate_old_chain(chain)

        elif any(
            not isinstance(block, dict) or "transactions" not in block
            for block in chain
        ):
            raise ValueError(
                "Blockchain contains mixed formats. "
                "Restore your backup before continuing."
            )

        if not validate_chain(chain):
            raise ValueError(
                "Saved blockchain failed validation. "
                "Do not delete or overwrite your backup."
            )

        return chain

    genesis = mine_block(1, "WTP-network", 0, "0", [])
    chain = [genesis]
    save_chain(chain)
    return chain


def load_pending():
    if not os.path.exists(PENDING_FILE):
        return []

    with open(PENDING_FILE, "r", encoding="utf-8") as file:
        pending = json.load(file)

    if not isinstance(pending, list):
        raise ValueError("Pending transactions file is invalid.")

    return pending


def save_pending(pending):
    temp_file = PENDING_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(pending, file, indent=2)

    os.replace(temp_file, PENDING_FILE)


def make_signed_transaction(
    private_key, public_bytes, sender, recipient, amount
):
    message_data = {
        "sender": sender,
        "recipient": recipient,
        "amount": amount
    }

    signature = private_key.sign(
        canonical(message_data).encode(),
        ec.ECDSA(hashes.SHA256())
    )

    return {
        **message_data,
        "public_key": public_bytes.hex(),
        "signature": signature.hex()
    }


def mine_next_block(chain, miner):
    issued = sum(block["reward"] for block in chain)
    reward = min(
        reward_for_block(chain[-1]["number"] + 1),
        MAX_SUPPLY - issued
    )

    if reward <= 0:
        print("Maximum WTP supply reached!")
        return

    pending = load_pending()
    current_balances = balances_for(chain)

    accepted = []
    reserved = {}

    for tx in pending:
        if not verify_transaction(tx):
            continue

        sender = tx["sender"]
        amount = tx["amount"]

        available = (
            current_balances.get(sender, 0)
            - reserved.get(sender, 0)
        )

        if amount <= available:
            accepted.append(tx)
            reserved[sender] = reserved.get(sender, 0) + amount

    difficulty = difficulty_for_next_block(chain)

    print("Mining difficulty:", difficulty)

    block = mine_block(
        chain[-1]["number"] + 1,
        miner,
        reward,
        chain[-1]["hash"],
        accepted,
        difficulty
    )

    chain.append(block)

    if not validate_chain(chain):
        chain.pop()
        raise ValueError(
            "New block failed validation. Blockchain not saved."
        )

    save_chain(chain)

    included = {canonical(tx) for tx in accepted}
    remaining = [
        tx for tx in pending
        if canonical(tx) not in included
    ]

    save_pending(remaining)

    print("Block mined and saved!")
    print("Block number:", block["number"])
    print("Block hash:", block["hash"])
    print("Miner reward:", block["reward"], "WTP")
    print("Transactions included:", len(accepted))


def main():
    chain = load_chain()

    print("=== WE THE PEOPLE (WTP) ===")
    print("Blockchain loaded successfully!")
    print("Blocks currently saved:", len(chain))
    print("WTP issued:", sum(b["reward"] for b in chain))

    private_key, public_bytes, address = load_wallet()

    print("Mining reward address:", address)
    print("Continuous mining started. Press Ctrl+C to stop.")

    try:
        while sum(b["reward"] for b in chain) < MAX_SUPPLY:
            old_length = len(chain)
            mine_next_block(chain, address)

            # Stop if mining did not append a block.
            if len(chain) == old_length:
                break

    except KeyboardInterrupt:
        print("\nMining stopped by user.")

    print("Blockchain valid:", validate_chain(chain))
    print(
        "Your wallet balance:",
        balances_for(chain).get(address, 0),
        "WTP"
    )
    print("Blocks currently saved:", len(chain))
    print("WTP issued:", sum(b["reward"] for b in chain))
    print("Saved file:", os.path.abspath(CHAIN_FILE))


import hashlib
import ecdsa


def generate_wtp_keypair():
    raw_private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    hex_private_key = raw_private_key.to_string().hex()

    raw_public_key = raw_private_key.get_verifying_key()
    bytes_public_key = raw_public_key.to_string()

    sha256_result = hashlib.sha256(bytes_public_key).digest()
    ripemd160_engine = hashlib.new('ripemd160')
    ripemd160_engine.update(sha256_result)

    wtp_wallet_address = f"wtp_{ripemd160_engine.hexdigest()}"

    return {
        "private_key": hex_private_key,
        "public_address": wtp_wallet_address
    }


if __name__ == "__main__":
    try:
        main()

    except (
        ValueError,
        KeyError,
        OSError,
        json.JSONDecodeError,
        TypeError
    ) as error:
        print("Problem:", error)