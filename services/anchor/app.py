from flask import Flask, request, jsonify

app = Flask(__name__)


@app.get("/health")
def health():
    return {"status": "ok", "service": "anchor"}


@app.post("/anchor")
def anchor():
    # TODO (Mohamed B.Y.): OpenTimestamps réel sur le hash + stockage en base (Postgres).
    return jsonify({
        "preuve_ots": "mock.ots",
        "horodatage": "2026-06-25T12:00:00Z",
        "reseau": "bitcoin (mock)",
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8003)
