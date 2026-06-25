import os

import requests
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
ORCH = os.getenv("ORCH_URL", "http://orchestrator:8080")

PAGE = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>AEGIS — Vérification de document</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px; color:#2C2C2A; }
    h1 { font-size: 22px; }
    button { background:#534AB7; color:#fff; border:0; padding:12px 20px; border-radius:8px; font-size:15px; cursor:pointer; }
    pre { background:#f4f4f2; padding:16px; border-radius:8px; overflow:auto; }
    .ok { color:#1D9E75; font-weight:700; }
  </style>
</head>
<body>
  <h1>🛡️ AEGIS — Vérification de document</h1>
  <p>Dépose un document puis lance la vérification (pipeline mock pour l'instant).</p>
  <input type="file" id="file">
  <p><button onclick="run()">Vérifier</button></p>
  <div id="out"></div>
  <script>
    async function run() {
      document.getElementById('out').innerHTML = 'Traitement…';
      const r = await fetch('/run', { method: 'POST' });
      const j = await r.json();
      document.getElementById('out').innerHTML =
        '<p class="ok">Passeport généré ✅</p><pre>' + JSON.stringify(j, null, 2) + '</pre>';
    }
  </script>
</body>
</html>"""


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.post("/run")
def run():
    # TODO (Sami): envoyer le vrai fichier à l'orchestrator + afficher passeport + QR.
    return jsonify(requests.post(f"{ORCH}/process", timeout=30).json())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
