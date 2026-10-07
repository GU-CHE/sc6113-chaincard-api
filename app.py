"""Small API for saving Ethereum mainnet transactions by verified hash."""

import os
import re
from datetime import datetime, timezone

import psycopg
import requests
from flask import Flask, jsonify, request
from psycopg.rows import dict_row


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024

FRONTEND_ORIGIN = os.environ.get(
    "FRONTEND_ORIGIN", "https://sc6113-chaincard.onrender.com"
).rstrip("/")
DATABASE_URL = os.environ.get("DATABASE_URL")
RPC_ENDPOINTS = [
    "https://ethereum-rpc.publicnode.com",
    "https://1rpc.io/eth",
    "https://cloudflare-eth.com",
]
TX_HASH = re.compile(r"^0x[a-fA-F0-9]{64}$")


@app.after_request
def cors(response):
    if request.headers.get("Origin") == FRONTEND_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = FRONTEND_ORIGIN
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def rpc(endpoint, method, params):
    response = requests.post(
        endpoint,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=8,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise ValueError(payload["error"].get("message", "RPC error"))
    return payload.get("result")


def chain_details(tx_hash):
    last_error = None
    for endpoint in RPC_ENDPOINTS:
        try:
            transaction = rpc(endpoint, "eth_getTransactionByHash", [tx_hash])
            if transaction is None:
                return None
            receipt = rpc(endpoint, "eth_getTransactionReceipt", [tx_hash])
            block = (
                rpc(endpoint, "eth_getBlockByNumber", [transaction["blockNumber"], False])
                if transaction.get("blockNumber")
                else None
            )
            status = "pending"
            if receipt and receipt.get("status") is not None:
                status = "success" if int(receipt["status"], 16) == 1 else "failed"
            return {
                "chain_id": 1,
                "tx_hash": transaction["hash"].lower(),
                "from_address": transaction["from"].lower(),
                "to_address": transaction["to"].lower() if transaction.get("to") else None,
                "value_wei": str(int(transaction["value"], 16)),
                "block_number": int(transaction["blockNumber"], 16) if transaction.get("blockNumber") else None,
                "block_time": datetime.fromtimestamp(int(block["timestamp"], 16), timezone.utc) if block else None,
                "status": status,
            }
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            last_error = error
    raise RuntimeError("Ethereum RPC is temporarily unavailable") from last_error


def db_connect():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def public_record(row):
    return {
        **row,
        "value_wei": str(row["value_wei"]),
        "block_time": row["block_time"].isoformat() if row["block_time"] else None,
        "saved_at": row["saved_at"].isoformat(),
    }


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.route("/api/transactions", methods=["GET", "POST", "OPTIONS"])
def transactions():
    if request.method == "OPTIONS":
        return ("", 204)
    try:
        if request.method == "GET":
            with db_connect() as connection:
                rows = connection.execute(
                    "SELECT chain_id, tx_hash, from_address, to_address, value_wei, "
                    "block_number, block_time, status, saved_at "
                    "FROM transactions ORDER BY saved_at DESC LIMIT 30"
                ).fetchall()
            return jsonify({"transactions": [public_record(row) for row in rows]})

        data = request.get_json(silent=True) or {}
        tx_hash = data.get("tx_hash", "")
        if not isinstance(tx_hash, str) or not TX_HASH.fullmatch(tx_hash):
            return jsonify({"error": "请输入有效的以太坊交易哈希（0x 加 64 位十六进制字符）。"}), 400
        details = chain_details(tx_hash)
        if details is None:
            return jsonify({"error": "以太坊主网上找不到这笔交易。"}), 404
        with db_connect() as connection:
            row = connection.execute(
                """INSERT INTO transactions
                   (chain_id, tx_hash, from_address, to_address, value_wei,
                    block_number, block_time, status)
                   VALUES (%(chain_id)s, %(tx_hash)s, %(from_address)s,
                    %(to_address)s, %(value_wei)s, %(block_number)s,
                    %(block_time)s, %(status)s)
                   ON CONFLICT (chain_id, tx_hash) DO UPDATE SET
                     block_number = EXCLUDED.block_number,
                     block_time = EXCLUDED.block_time,
                     status = EXCLUDED.status
                   RETURNING chain_id, tx_hash, from_address, to_address,
                             value_wei, block_number, block_time, status, saved_at""",
                details,
            ).fetchone()
        return jsonify({"transaction": public_record(row)}), 201
    except psycopg.Error:
        app.logger.exception("Database request failed")
        return jsonify({"error": "数据库暂时不可用。"}), 503
    except RuntimeError:
        app.logger.exception("External service unavailable")
        return jsonify({"error": "链上服务暂时不可用，请稍后重试。"}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
