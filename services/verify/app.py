from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/health")
def health():
    return {"status": "ok", "service": "verify"}


@app.get("/verify/<doc_id>")
def verify(doc_id):
    # TODO (Fatma): lookup réel en base + vérif on-chain + génération / scan du QR.
    return jsonify({
        "id": doc_id,
        "statut": "authentique",                # authentique | falsifie | inconnu
        "preuve_onchain": "MOCK",
        "verifie_le": "2026-06-25T12:00:00Z",
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8004)
