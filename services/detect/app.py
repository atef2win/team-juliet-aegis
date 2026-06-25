import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

SIGHT_USER   = os.getenv("SIGHTENGINE_USER", "")
SIGHT_SECRET = os.getenv("SIGHTENGINE_SECRET", "")
SIGHT_URL    = "https://api.sightengine.com/1.0/check.json"

FAKE_THRESHOLD       = 0.6
SUSPICIOUS_THRESHOLD = 0.3


@app.get("/health")
def health():
    return {"status": "ok", "service": "detect"}


@app.post("/detect")
def detect():
    fichier = request.files.get("file") or request.files.get("fichier")
    if not fichier:
        return jsonify({"error": "Aucun fichier reçu"}), 400

    # ── Appel Sightengine ──────────────────────────────────────────────
    response = requests.post(
        SIGHT_URL,
        files={"media": (fichier.filename, fichier.read(), fichier.content_type)},
        data={
            "models": "deepfake,genai",
            "api_user": SIGHT_USER,
            "api_secret": SIGHT_SECRET,
        },
        timeout=15
    )
    result = response.json()

    # ── Calcul du score ────────────────────────────────────────────────
    score_deepfake = result.get("deepfake", {}).get("score", 0.0)
    score_genai    = result.get("ai_generated", {}).get("score", 0.0)
    score_fake     = round(max(score_deepfake, score_genai), 4)

    if score_fake >= FAKE_THRESHOLD:
        verdict = "fake"
    elif score_fake >= SUSPICIOUS_THRESHOLD:
        verdict = "suspicious"
    else:
        verdict = "authentic"

    signaux = []
    if score_deepfake > 0.3:
        signaux.append(f"Deepfake détecté : {score_deepfake:.2%}")
    if score_genai > 0.3:
        signaux.append(f"Image IA générée : {score_genai:.2%}")
    if not signaux:
        signaux.append("Aucune anomalie détectée")

    return jsonify({
        "verdict": verdict,
        "score": round(1 - score_fake, 4),
        "signaux": signaux,
        "explication": (
            f"Score deepfake: {score_deepfake:.2%} · "
            f"Score IA-généré: {score_genai:.2%} · "
            f"Verdict: {verdict}"
        ),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)