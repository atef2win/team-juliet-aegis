import os
import io

import psycopg2
import qrcode
from flask import Flask, jsonify, send_file, render_template_string

app = Flask(__name__)

PG = dict(
    host=os.getenv("PGHOST", "db"),
    dbname=os.getenv("PGDATABASE", "aegis"),
    user=os.getenv("PGUSER", "aegis"),
    password=os.getenv("PGPASSWORD", "aegis"),
)
# URL publique (via ngrok/passerelle) encodee dans le QR pour etre scannable au telephone
PUBLIC_BASE = os.getenv("PUBLIC_BASE", "http://localhost:8004").rstrip("/")


def fetch_proof(doc_id):
    conn = psycopg2.connect(**PG)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, hash, ots, reseau, horodatage FROM preuves WHERE id=%s",
                (doc_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AEGIS - Verification</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:560px;margin:32px auto;padding:0 16px;color:#2C2C2A}
 .card{border:1px solid #D3D1C7;border-radius:14px;padding:24px;text-align:center}
 .ok{color:#1D9E75}.ko{color:#E24B4A}
 .badge{font-size:46px;line-height:1}
 table{width:100%;margin-top:18px;border-collapse:collapse;font-size:13px;text-align:left}
 td{padding:7px 4px;border-bottom:1px solid #eee;word-break:break-all}
 td:first-child{color:#888;width:36%}
 img{margin-top:18px;width:170px;height:170px}
 h1{font-size:20px;margin:8px 0}
</style></head><body>
<div class="card">
{% if found %}
  <div class="badge ok">&#9989;</div>
  <h1 class="ok">Document authentique</h1>
  <p>Preuve verifiee &mdash; scellee et ancree par AEGIS.</p>
  <table>
    <tr><td>Identifiant</td><td>{{ id }}</td></tr>
    <tr><td>Empreinte (hash)</td><td>{{ hash }}</td></tr>
    <tr><td>Reseau d'ancrage</td><td>{{ reseau }}</td></tr>
    <tr><td>Horodatage</td><td>{{ horodatage }}</td></tr>
  </table>
  <img src="{{ qr }}" alt="QR de verification">
{% else %}
  <div class="badge ko">&#9940;</div>
  <h1 class="ko">Preuve introuvable</h1>
  <p>Aucun document AEGIS pour l'identifiant <b>{{ id }}</b>.</p>
{% endif %}
  <p style="margin-top:20px;color:#888;font-size:12px">&#128737; AEGIS &mdash; Digital Trust Hub</p>
</div></body></html>"""


@app.get("/health")
def health():
    return {"status": "ok", "service": "verify"}


@app.get("/verify/<doc_id>/qr")
def qr(doc_id):
    img = qrcode.make(f"{PUBLIC_BASE}/verify/{doc_id}")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.get("/verify/<doc_id>/json")
def verify_json(doc_id):
    row = fetch_proof(doc_id)
    if not row:
        return jsonify({"id": doc_id, "statut": "inconnu"}), 404
    return jsonify({
        "id": row[0],
        "statut": "authentique",
        "hash": row[1],
        "preuve_onchain": row[2],
        "reseau": row[3],
        "horodatage": row[4].isoformat() if row[4] else None,
    })


@app.get("/verify/<doc_id>")
def verify_page(doc_id):
    row = fetch_proof(doc_id)
    if not row:
        return render_template_string(PAGE, found=False, id=doc_id), 404
    return render_template_string(
        PAGE,
        found=True,
        id=row[0],
        hash=row[1],
        reseau=row[3],
        horodatage=row[4].isoformat() if row[4] else "",
        qr=f"{PUBLIC_BASE}/verify/{row[0]}/qr",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8004)
