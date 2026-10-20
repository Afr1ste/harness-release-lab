"""A faultable test business, not a production gateway or an untrusted-code sandbox."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

from .models import Operation, Scenario


class World:
    def __init__(self, db: Path, scenario: Scenario):
        self.db = db
        self.scenario = scenario
        db.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS effects (
                  id INTEGER PRIMARY KEY, operation_key TEXT UNIQUE NOT NULL,
                  payload_hash TEXT NOT NULL, order_id TEXT NOT NULL,
                  amount_cents INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                  seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (
                  id INTEGER PRIMARY KEY, operation_key TEXT NOT NULL, fault TEXT NOT NULL);
            """)

    def connect(self):
        con = sqlite3.connect(self.db, timeout=10)
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def event(con, kind, **data):
        con.execute("INSERT INTO events(kind,data) VALUES (?,?)", (kind, json.dumps(data)))

    def note(self, kind: str, **data):
        with self.connect() as con:
            self.event(con, kind, **data)

    def apply(self, key: str, operation: Operation) -> tuple[int, dict, float]:
        payload = operation.model_dump()
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with self.connect() as con:
            # The unique key and read/insert decision belong to one database transaction.
            con.execute("BEGIN IMMEDIATE")
            attempt = con.execute("SELECT count(*) FROM attempts").fetchone()[0] + 1
            fault = (
                self.scenario.faults[attempt - 1]
                if attempt <= len(self.scenario.faults)
                else "none"
            )
            con.execute("INSERT INTO attempts VALUES (?,?,?)", (attempt, key, fault))
            self.event(con, "request", attempt=attempt, operation_key=key, payload=payload)
            if fault != "none":
                self.event(con, "fault", attempt=attempt, fault=fault)
            if fault in ("before_429", "before_503", "denied"):
                status = {"before_429": 429, "before_503": 503, "denied": 403}[fault]
                self.event(
                    con, "response_prepared", attempt=attempt, status=status, committed=False
                )
                return status, {"error": fault, "attempt": attempt}, 0
            row = con.execute("SELECT * FROM effects WHERE operation_key=?", (key,)).fetchone()
            if row and row["payload_hash"] != payload_hash:
                self.event(con, "key_conflict", attempt=attempt, operation_key=key)
                return 409, {"error": "idempotency_key_payload_mismatch"}, 0
            if row is None:
                cursor = con.execute(
                    "INSERT INTO effects(operation_key,payload_hash,order_id,amount_cents)"
                    " VALUES (?,?,?,?)",
                    (key, payload_hash, operation.order_id, operation.amount_cents),
                )
                receipt = cursor.lastrowid
                self.event(con, "commit", attempt=attempt, receipt_id=receipt, **payload)
            else:
                receipt = row["id"]
                self.event(con, "deduplicated", attempt=attempt, receipt_id=receipt)
            status = 503 if fault == "after_503" else 200
            delay = 0.6 if fault == "after_timeout" else 0
            self.event(
                con, "response_prepared", attempt=attempt, status=status, delay_ms=int(delay * 1000)
            )
            body = (
                {"error": "response_lost", "attempt": attempt}
                if status == 503
                else {"receipt_id": receipt, "status": "committed"}
            )
            return status, body, delay

    def snapshot(self) -> dict:
        with self.connect() as con:
            return {
                "effects": [dict(r) for r in con.execute("SELECT * FROM effects ORDER BY id")],
                "events": [
                    {"seq": r["seq"], "kind": r["kind"], **json.loads(r["data"])}
                    for r in con.execute("SELECT * FROM events ORDER BY seq")
                ],
                "attempts": con.execute("SELECT count(*) FROM attempts").fetchone()[0],
            }


def deliver(world: World, key: str, operation: Operation):
    status, body, delay = world.apply(key, operation)
    # apply() has committed before we simulate the missing/late acknowledgement.
    if delay:
        time.sleep(delay)
    return status, body
