# WTP Coin — Public Source Test

This is a source-code test release, not a production-ready public network.

## Safety
- Do not copy private keys, wallet files, pending transactions, or your live blockchain into this folder.
- Do not expose mining or block-submission endpoints to the public internet.
- Peer data is read-only and does not provide peer synchronization.
- Review and test consensus rules and transaction validation before public deployment.

## Python dependencies
Install dependencies with: python -m pip install -r requirements.txt

## Included source
- wtp_coin.py
- wtp_peer_server.py
- wtp_node_server.py
- wtp_mining_server.py
- wtp_readonly_api.py

The internet-facing block-submission server is intentionally excluded pending further review.
