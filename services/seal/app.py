from flask import Flask, request, jsonify

app = Flask(__name__)


@app.get("/health")
def health():
    return {"status": "ok", "service": "seal"}


@app.post("/seal")
def seal():
    # TODO (Romuald): hash SHA-256 réel du fichier + signature C2PA (c2patool) + clé/DID.
    return jsonify({
        "hash": "MOCKSHA256",
        "signature": "MOCKSIG",
        "fichier_signe": "mock.c2pa",
        "did": "did:key:MOCK",
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8002)
