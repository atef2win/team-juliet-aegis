import os
import socket
import time
import uuid
import base64
import binascii
from datetime import datetime, timezone

import psycopg2
from flask import Flask, request, jsonify

# Évite tout blocage réseau (calendriers OpenTimestamps) pendant la démo
socket.setdefaulttimeout(10)

app = Flask(__name__)

PG = dict(
    host=os.getenv("PGHOST", "db"),
    dbname=os.getenv("PGDATABASE", "aegis"),
    user=os.getenv("PGUSER", "aegis"),
    password=os.getenv("PGPASSWORD", "aegis"),
)


def db_exec(query, params=None):
    conn = psycopg2.connect(**PG)
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
        conn.commit()
    finally:
        conn.close()


def init_db(retries=25):
    for _ in range(retries):
        try:
            db_exec(
                """CREATE TABLE IF NOT EXISTS preuves (
                    id TEXT PRIMARY KEY,
                    hash TEXT NOT NULL,
                    ots TEXT,
                    reseau TEXT,
                    horodatage TIMESTAMPTZ NOT NULL DEFAULT now()
                )"""
            )
            print("DB prete", flush=True)
            return True
        except Exception as e:
            print(f"DB pas prete, retry... ({e})", flush=True)
            time.sleep(2)
    return False


def make_ots(hash_hex):
    """Ancrage OpenTimestamps reel sur le hash. Fallback horodate si indispo
    (hash non-SHA256 ou reseau injoignable) -> la demo ne casse jamais."""
    try:
        digest = binascii.unhexlify(hash_hex)
        if len(digest) != 32:
            raise ValueError("le hash n'est pas un SHA-256 (32 octets)")
        from opentimestamps.core.timestamp import Timestamp
        from opentimestamps.core.serialize import BytesSerializationContext
        from opentimestamps.calendar import RemoteCalendar

        ts = Timestamp(digest)
        cal = RemoteCalendar("https://a.pool.opentimestamps.org")
        ts.merge(cal.submit(digest))
        ctx = BytesSerializationContext()
        ts.serialize(ctx)
        return base64.b64encode(ctx.getbytes()).decode(), "bitcoin (OpenTimestamps)"
    except Exception as e:
        token = base64.b64encode(
            f"{hash_hex}|{datetime.now(timezone.utc).isoformat()}".encode()
        ).decode()
        return token, f"horodatage local (fallback: {type(e).__name__})"


@app.get("/health")
def health():
    return {"status": "ok", "service": "anchor"}


@app.post("/anchor")
def anchor():
    data = request.get_json(silent=True) or {}
    hash_hex = str(data.get("hash", "")).strip()
    doc_id = uuid.uuid4().hex[:12]
    ots, reseau = make_ots(hash_hex)
    horodatage = datetime.now(timezone.utc).isoformat()
    stored = True
    try:
        db_exec(
            "INSERT INTO preuves (id, hash, ots, reseau, horodatage) VALUES (%s,%s,%s,%s,%s)",
            (doc_id, hash_hex, ots, reseau, horodatage),
        )
    except Exception as e:
        stored = False
        print(f"INSERT KO: {e}", flush=True)
    return jsonify({
        "id": doc_id,
        "preuve_ots": ots,
        "horodatage": horodatage,
        "reseau": reseau,
        "stored": stored,
    })


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8003)
