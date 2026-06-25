from flask import Flask, request, jsonify

app = Flask(__name__)


@app.get("/health")
def health():
    return {"status": "ok", "service": "detect"}


@app.post("/detect")
def detect():
    # TODO (Mariem): OCR (Tesseract / Google Document AI) puis détection réelle :
    #   intégrité (hash), métadonnées/EXIF, anomalies visuelles, Hive / Sightengine.
    # Garde EXACTEMENT ce format de sortie (cf. contracts/contracts.md).
    return jsonify({
        "verdict": "authentic",                 # authentic | suspicious | fake
        "score": 0.97,
        "signaux": ["MOCK: aucune anomalie détectée"],
        "explication": "MOCK — remplacer par la vraie détection",
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
