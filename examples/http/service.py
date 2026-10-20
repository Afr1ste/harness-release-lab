"""Disposable order service for the integration recipe. No dependency on lab internals."""

import hashlib
import json
import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


class Order(BaseModel):
    run_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    sku: str = Field(min_length=1, max_length=100)
    units: int = Field(gt=0, le=100)


def create_app(database: Path | None = None):
    database = database or Path(os.environ.get("ORDER_DATABASE", ".lab/orders.sqlite"))
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS orders "
            "(id INTEGER PRIMARY KEY, key TEXT UNIQUE, payload_hash TEXT, run_id TEXT, units INT)"
        )
    app = FastAPI()

    @app.post("/orders")
    def order(payload: Order, idempotency_key: str = Header(min_length=1, max_length=200)):
        digest = hashlib.sha256(
            json.dumps(payload.model_dump(), sort_keys=True).encode()
        ).hexdigest()
        with sqlite3.connect(database, timeout=10) as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT id,payload_hash FROM orders WHERE key=?", (idempotency_key,)
            ).fetchone()
            if previous:
                if previous[1] != digest:
                    raise HTTPException(409, "key reused for different payload")
                return {"id": previous[0], "deduplicated": True}
            cursor = db.execute(
                "INSERT INTO orders(key,payload_hash,run_id,units) VALUES (?,?,?,?)",
                (idempotency_key, digest, payload.run_id, payload.units),
            )
            return {"id": cursor.lastrowid, "deduplicated": False}

    @app.get("/state/{run_id}")
    def state(run_id: str):
        with sqlite3.connect(database) as db:
            count, units = db.execute(
                "SELECT COUNT(*),COALESCE(SUM(units),0) FROM orders WHERE run_id=?", (run_id,)
            ).fetchone()
        return {"orders": count, "units": units}

    return app
