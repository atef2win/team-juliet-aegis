import os
import uuid

import requests
from flask import Flask, jsonify

app = Flask(__name__)

DETECT = os.getenv("DETECT_URL", "http://detect:8001")
SEAL = os.getenv("SEAL_URL", "http://seal:8002")
ANCHOR = os.getenv("ANCHOR_URL", "http://anchor:8003")


@app.get("/health")
def health():
    return {"status": "ok", "service": "orchestrator"}


@app.post("/process")
def process():
    # En PRODUCTION ce rôle est tenu par n8n. Ici = orchestrateur local pour le dev / la démo.
    doc_id = uuid.uuid4().hex[:8]
    detection = requests.post(f"{DETECT}/detect", timeout=10).json()
    seal = requests.post(f"{SEAL}/seal", timeout=10).json()
    anchor = requests.post(f"{ANCHOR}/anchor", timeout=10).json()
    return jsonify({
        "id": doc_id,
        "detection": detection,
        "seal": seal,
        "anchor": anchor,
        "passeport": f"/verify/{doc_id}",
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
