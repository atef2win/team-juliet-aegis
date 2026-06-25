import os
import io
import json
import base64
import hashlib
import uuid
import random
from datetime import datetime
import requests
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)
ORCH = os.getenv("ORCH_URL", "http://orchestrator:8080")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ─── HTML TEMPLATE ────────────────────────────────────────────────────────────
PAGE = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AEGIS — Vérification de document</title>
  <style>
    :root {
      --navy:    #0D1B2A;
      --navy2:   #152336;
      --navy3:   #1E3250;
      --amber:   #F5A623;
      --amber2:  #E8940D;
      --green:   #1DB87C;
      --red:     #E8455A;
      --white:   #F8F7F4;
      --muted:   #8A99AE;
      --border:  rgba(255,255,255,0.08);
      --mono: 'JetBrains Mono', 'Fira Mono', 'Courier New', monospace;
      --sans: 'Inter', system-ui, sans-serif;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: var(--navy);
      color: var(--white);
      font-family: var(--sans);
      min-height: 100vh;
      padding: 0 16px 60px;
    }

    /* ── NAV ── */
    nav {
      display: flex; align-items: center; gap: 12px;
      padding: 20px 0 24px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 40px;
    }
    .nav-logo {
      font-family: var(--mono);
      font-size: 13px;
      color: var(--amber);
      letter-spacing: 0.15em;
      text-transform: uppercase;
    }
    .nav-badge {
      font-family: var(--mono);
      font-size: 10px;
      background: rgba(245,166,35,0.15);
      border: 1px solid rgba(245,166,35,0.3);
      color: var(--amber);
      padding: 2px 8px;
      border-radius: 100px;
      letter-spacing: 0.1em;
    }

    /* ── LAYOUT ── */
    .wrap { max-width: 780px; margin: 0 auto; }

    h1 {
      font-size: clamp(22px, 4vw, 32px);
      font-weight: 700;
      line-height: 1.2;
      margin-bottom: 10px;
    }
    .subtitle {
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 36px;
    }

    /* ── UPLOAD ZONE ── */
    .upload-zone {
      border: 2px dashed var(--border);
      border-radius: 16px;
      padding: 40px 24px;
      text-align: center;
      cursor: pointer;
      transition: border-color .2s, background .2s;
      background: rgba(255,255,255,0.02);
      position: relative;
      margin-bottom: 20px;
    }
    .upload-zone:hover, .upload-zone.drag { border-color: var(--amber); background: rgba(245,166,35,0.04); }
    .upload-zone input { position:absolute; inset:0; opacity:0; cursor:pointer; width:100%; height:100%; }
    .upload-icon { font-size: 36px; margin-bottom: 12px; }
    .upload-label { font-size: 15px; font-weight: 600; margin-bottom: 6px; }
    .upload-hint { font-size: 12px; color: var(--muted); }
    .file-name {
      margin-top: 12px;
      font-family: var(--mono);
      font-size: 12px;
      color: var(--amber);
      display: none;
    }

    /* ── DOC TYPE SELECTOR ── */
    .doc-types {
      display: flex; flex-wrap: wrap; gap: 8px;
      margin-bottom: 24px;
    }
    .doc-type {
      padding: 8px 16px;
      border-radius: 100px;
      border: 1px solid var(--border);
      background: transparent;
      color: var(--muted);
      font-size: 13px;
      cursor: pointer;
      transition: all .15s;
      font-family: var(--sans);
    }
    .doc-type:hover { border-color: var(--amber); color: var(--amber); }
    .doc-type.active {
      background: rgba(245,166,35,0.15);
      border-color: var(--amber);
      color: var(--amber);
      font-weight: 600;
    }

    /* ── BUTTON ── */
    .btn {
      background: var(--amber);
      color: var(--navy);
      border: 0;
      padding: 14px 28px;
      border-radius: 10px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      transition: background .15s, transform .1s;
      width: 100%;
      letter-spacing: 0.01em;
    }
    .btn:hover { background: var(--amber2); }
    .btn:active { transform: scale(.98); }
    .btn:disabled { opacity: .5; cursor: not-allowed; }

    /* ── SCANNER ANIMATION ── */
    #scanner {
      display: none;
      background: var(--navy2);
      border-radius: 16px;
      padding: 32px 24px;
      margin-top: 28px;
      text-align: center;
      border: 1px solid var(--border);
    }
    .scan-box {
      width: 180px; height: 130px;
      border: 2px solid var(--amber);
      border-radius: 8px;
      margin: 0 auto 20px;
      position: relative;
      overflow: hidden;
    }
    .scan-line {
      position: absolute; left: 0; right: 0; height: 2px;
      background: linear-gradient(90deg, transparent, var(--amber), transparent);
      animation: scan 1.6s ease-in-out infinite;
      box-shadow: 0 0 12px var(--amber);
    }
    @keyframes scan { 0%,100% { top: 0; } 50% { top: calc(100% - 2px); } }
    .scan-corners::before, .scan-corners::after {
      content: ''; position: absolute; width: 16px; height: 16px;
      border-color: var(--amber); border-style: solid;
    }
    .scan-corners::before { top: -2px; left: -2px; border-width: 3px 0 0 3px; }
    .scan-corners::after  { bottom: -2px; right: -2px; border-width: 0 3px 3px 0; }
    .scan-status { font-family: var(--mono); font-size: 12px; color: var(--amber); letter-spacing: 0.1em; }
    .scan-steps { margin-top: 16px; text-align: left; }
    .scan-step {
      font-family: var(--mono); font-size: 11px; color: var(--muted);
      padding: 3px 0; transition: color .3s;
    }
    .scan-step.done { color: var(--green); }
    .scan-step.active { color: var(--white); }

    /* ── RESULT CARD ── */
    #result { display: none; margin-top: 28px; }

    .verdict-banner {
      border-radius: 14px 14px 0 0;
      padding: 28px 28px 20px;
      display: flex; align-items: center; gap: 16px;
    }
    .verdict-banner.authentic { background: rgba(29,184,124,0.12); border: 1px solid rgba(29,184,124,0.3); }
    .verdict-banner.forged    { background: rgba(232,69,90,0.12);  border: 1px solid rgba(232,69,90,0.3); }
    .verdict-icon { font-size: 40px; }
    .verdict-label { font-size: 22px; font-weight: 800; letter-spacing: -0.01em; }
    .verdict-sub   { font-size: 13px; color: var(--muted); margin-top: 3px; }

    /* confidence bar */
    .conf-bar-wrap {
      background: var(--navy2);
      border-left: 1px solid var(--border);
      border-right: 1px solid var(--border);
      padding: 20px 28px;
    }
    .conf-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.12em; color: var(--muted); margin-bottom: 8px; }
    .conf-bar {
      height: 8px; border-radius: 100px;
      background: rgba(255,255,255,0.08);
      overflow: hidden; margin-bottom: 6px;
    }
    .conf-fill {
      height: 100%; border-radius: 100px;
      background: linear-gradient(90deg, var(--amber), var(--green));
      transition: width 1s cubic-bezier(.4,0,.2,1);
      width: 0;
    }
    .conf-fill.low { background: linear-gradient(90deg, var(--amber), var(--red)); }
    .conf-value { font-family: var(--mono); font-size: 20px; font-weight: 700; }

    /* passport */
    .passport {
      background: var(--navy2);
      border: 1px solid var(--border);
      border-top: 0;
      border-radius: 0 0 14px 14px;
      padding: 24px 28px;
    }
    .passport-title {
      font-family: var(--mono);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.15em;
      color: var(--amber);
      margin-bottom: 16px;
    }
    .passport-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }
    @media (max-width: 500px) { .passport-grid { grid-template-columns: 1fr; } }
    .pp-field { }
    .pp-key { font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin-bottom: 4px; }
    .pp-val { font-family: var(--mono); font-size: 13px; word-break: break-all; }
    .pp-val.hash { font-size: 10px; color: var(--muted); }

    /* signals deck */
    .signals { margin-top: 20px; }
    .signals-title {
      font-size: 11px; text-transform: uppercase; letter-spacing: 0.12em;
      color: var(--muted); margin-bottom: 12px;
    }
    .signal-row {
      display: flex; align-items: center; gap: 10px;
      padding: 10px 0;
      border-bottom: 1px solid var(--border);
      font-size: 13px;
    }
    .signal-row:last-child { border-bottom: 0; }
    .sig-icon { font-size: 16px; flex-shrink: 0; }
    .sig-name { flex: 1; }
    .sig-badge {
      font-family: var(--mono); font-size: 10px;
      padding: 3px 8px; border-radius: 100px;
      letter-spacing: 0.05em;
    }
    .sig-badge.ok  { background: rgba(29,184,124,0.15); color: var(--green); }
    .sig-badge.warn{ background: rgba(245,166,35,0.15);  color: var(--amber); }
    .sig-badge.fail{ background: rgba(232,69,90,0.15);   color: var(--red);  }

    /* QR placeholder */
    .qr-section {
      margin-top: 20px;
      display: flex; align-items: center; gap: 20px;
      padding: 16px 20px;
      background: rgba(245,166,35,0.05);
      border: 1px solid rgba(245,166,35,0.15);
      border-radius: 10px;
    }
    .qr-box {
      width: 72px; height: 72px; flex-shrink: 0;
      background: var(--white); border-radius: 6px;
      display: flex; align-items: center; justify-content: center;
      font-size: 36px;
    }
    .qr-info { font-size: 12px; color: var(--muted); line-height: 1.6; }
    .qr-id { font-family: var(--mono); font-size: 11px; color: var(--amber); margin-top: 4px; }

    /* reset */
    .reset-btn {
      margin-top: 16px;
      background: transparent;
      border: 1px solid var(--border);
      color: var(--muted);
      padding: 10px 20px;
      border-radius: 8px;
      font-size: 13px;
      cursor: pointer;
      width: 100%;
      transition: all .15s;
    }
    .reset-btn:hover { border-color: var(--muted); color: var(--white); }
  </style>
</head>
<body>
<div class="wrap">

  <nav>
    <span class="nav-logo">🛡️ AEGIS</span>
    <span class="nav-badge">BETA v0.3</span>
  </nav>

  <h1>Vérification de<br>documents officiels</h1>
  <p class="subtitle">Détectez les falsifications — diplômes, certifications, factures, passeports et plus.</p>

  <!-- TYPE SELECTOR -->
  <div class="doc-types" id="docTypes">
    <button class="doc-type active" data-type="auto">🔍 Détection auto</button>
    <button class="doc-type" data-type="diplome">🎓 Diplôme</button>
    <button class="doc-type" data-type="certification">📜 Certification</button>
    <button class="doc-type" data-type="facture">🧾 Facture</button>
    <button class="doc-type" data-type="passeport">🛂 Passeport / ID</button>
    <button class="doc-type" data-type="contrat">📋 Contrat</button>
  </div>

  <!-- UPLOAD -->
  <div class="upload-zone" id="dropZone">
    <input type="file" id="fileInput" accept="image/*,application/pdf,.jpg,.jpeg,.png,.pdf">
    <div class="upload-icon">📄</div>
    <div class="upload-label">Glisser un document ici</div>
    <div class="upload-hint">PDF, JPG, PNG · max 10 Mo</div>
    <div class="file-name" id="fileName"></div>
  </div>

  <button class="btn" id="verifyBtn" onclick="verify()">Analyser le document</button>

  <!-- SCANNER -->
  <div id="scanner">
    <div class="scan-box">
      <div class="scan-corners"></div>
      <div class="scan-line"></div>
    </div>
    <div class="scan-status" id="scanStatus">INITIALISATION…</div>
    <div class="scan-steps" id="scanSteps"></div>
  </div>

  <!-- RESULT -->
  <div id="result"></div>

</div>

<script>
// ── doc type selection ──
let selectedType = 'auto';
document.querySelectorAll('.doc-type').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.doc-type').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedType = btn.dataset.type;
  });
});

// ── drag & drop ──
const zone = document.getElementById('dropZone');
const inp  = document.getElementById('fileInput');
const fn   = document.getElementById('fileName');

zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag'); });
zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
zone.addEventListener('drop', e => {
  e.preventDefault(); zone.classList.remove('drag');
  if (e.dataTransfer.files[0]) { inp.files = e.dataTransfer.files; showFileName(); }
});
inp.addEventListener('change', showFileName);

function showFileName() {
  if (inp.files[0]) {
    fn.textContent = '📎 ' + inp.files[0].name;
    fn.style.display = 'block';
  }
}

// ── scanner steps ──
const STEPS = [
  'Extraction des métadonnées',
  'Analyse des pixels et artefacts JPEG',
  'Vérification des polices & encodage',
  'Contrôle des signatures numériques',
  'Détection IA des zones modifiées',
  'Score de confiance final',
];

function animateSteps(callback) {
  const container = document.getElementById('scanSteps');
  container.innerHTML = '';
  STEPS.forEach((s, i) => {
    const el = document.createElement('div');
    el.className = 'scan-step';
    el.id = 'step_' + i;
    el.textContent = '○ ' + s;
    container.appendChild(el);
  });

  let i = 0;
  function next() {
    if (i > 0) {
      document.getElementById('step_' + (i-1)).className = 'scan-step done';
      document.getElementById('step_' + (i-1)).textContent = '✓ ' + STEPS[i-1];
    }
    if (i < STEPS.length) {
      const el = document.getElementById('step_' + i);
      el.className = 'scan-step active';
      el.textContent = '▶ ' + STEPS[i];
      document.getElementById('scanStatus').textContent = STEPS[i].toUpperCase() + '…';
      i++;
      setTimeout(next, 600 + Math.random() * 400);
    } else {
      document.getElementById('scanStatus').textContent = 'ANALYSE COMPLÈTE';
      setTimeout(callback, 400);
    }
  }
  next();
}

// ── verify ──
async function verify() {
  if (!inp.files[0]) { alert('Veuillez sélectionner un document.'); return; }

  document.getElementById('verifyBtn').disabled = true;
  document.getElementById('scanner').style.display = 'block';
  document.getElementById('result').style.display = 'none';

  const formData = new FormData();
  formData.append('file', inp.files[0]);
  formData.append('doc_type', selectedType);

  // Start API call in parallel with animation
  const apiPromise = fetch('/analyze', { method: 'POST', body: formData });

  animateSteps(async () => {
    try {
      const resp = await apiPromise;
      const data = await resp.json();
      document.getElementById('scanner').style.display = 'none';
      renderResult(data);
    } catch (e) {
      document.getElementById('scanner').style.display = 'none';
      document.getElementById('result').innerHTML =
        '<p style="color:var(--red);font-family:var(--mono);font-size:13px">Erreur: ' + e.message + '</p>';
      document.getElementById('result').style.display = 'block';
    }
    document.getElementById('verifyBtn').disabled = false;
  });
}

// ── render result ──
function renderResult(d) {
  const isAuth = d.verdict === 'AUTHENTIQUE';
  const conf   = d.confidence_score || 0;
  const sig    = d.signals || [];

  const signalRows = sig.map(s => {
    const cls = s.status === 'ok' ? 'ok' : s.status === 'warn' ? 'warn' : 'fail';
    const label = s.status === 'ok' ? '✓ OK' : s.status === 'warn' ? '⚠ Suspect' : '✗ Anomalie';
    return `<div class="signal-row">
      <span class="sig-icon">${s.icon || '🔎'}</span>
      <span class="sig-name">${s.name}</span>
      <span class="sig-badge ${cls}">${label}</span>
    </div>`;
  }).join('');

  const pp = d.passport || {};
  const docId = 'AGS-' + Math.random().toString(36).slice(2,8).toUpperCase();

  document.getElementById('result').innerHTML = `
    <div class="verdict-banner ${isAuth ? 'authentic' : 'forged'}">
      <div class="verdict-icon">${isAuth ? '✅' : '🚨'}</div>
      <div>
        <div class="verdict-label" style="color:${isAuth ? 'var(--green)' : 'var(--red)'}">${d.verdict}</div>
        <div class="verdict-sub">${d.summary || ''}</div>
      </div>
    </div>

    <div class="conf-bar-wrap">
      <div class="conf-label">Score de confiance</div>
      <div class="conf-bar">
        <div class="conf-fill ${conf < 50 ? 'low' : ''}" id="confFill"></div>
      </div>
      <div class="conf-value" style="color:${isAuth ? 'var(--green)' : 'var(--red)'}">${conf}%</div>
    </div>

    <div class="passport">
      <div class="passport-title">📋 Passeport du document</div>
      <div class="passport-grid">
        <div class="pp-field"><div class="pp-key">Type détecté</div><div class="pp-val">${pp.doc_type || d.detected_type || '—'}</div></div>
        <div class="pp-field"><div class="pp-key">Émetteur</div><div class="pp-val">${pp.issuer || '—'}</div></div>
        <div class="pp-field"><div class="pp-key">Date d'émission</div><div class="pp-val">${pp.issue_date || '—'}</div></div>
        <div class="pp-field"><div class="pp-key">Titulaire</div><div class="pp-val">${pp.holder || '—'}</div></div>
        <div class="pp-field" style="grid-column:1/-1">
          <div class="pp-key">Hash SHA-256</div>
          <div class="pp-val hash">${pp.file_hash || '—'}</div>
        </div>
      </div>

      <div class="signals">
        <div class="signals-title">Signaux d'analyse (${sig.length} vérifications)</div>
        ${signalRows || '<div style="color:var(--muted);font-size:13px">Aucun signal disponible</div>'}
      </div>

      <div class="qr-section">
        <div class="qr-box">🔲</div>
        <div>
          <div class="qr-info">QR de vérification — scannez pour valider l'authenticité sur le registre AEGIS.</div>
          <div class="qr-id">${docId}</div>
          <div class="qr-info" style="margin-top:4px">Analysé le ${new Date().toLocaleDateString('fr-FR', {day:'2-digit',month:'long',year:'numeric'})}</div>
        </div>
      </div>
    </div>

    <button class="reset-btn" onclick="resetUI()">↩ Analyser un autre document</button>
  `;
  document.getElementById('result').style.display = 'block';

  // animate bar
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.getElementById('confFill').style.width = conf + '%';
    });
  });
}

function resetUI() {
  document.getElementById('result').style.display = 'none';
  inp.value = '';
  fn.style.display = 'none';
  fn.textContent = '';
}
</script>
</body>
</html>"""


# ─── ANALYSIS ROUTE ───────────────────────────────────────────────────────────

def build_analysis_prompt(doc_type: str, filename: str) -> str:
    type_hints = {
        "diplome":       "un diplôme universitaire ou scolaire",
        "certification": "une certification professionnelle (ex: AWS, PMP, Cisco)",
        "facture":       "une facture commerciale ou administrative",
        "passeport":     "un passeport ou document d'identité officiel",
        "contrat":       "un contrat ou accord légal",
        "auto":          "un document officiel (type inconnu — détecter automatiquement)",
    }
    doc_hint = type_hints.get(doc_type, "un document officiel")

    return f"""Tu es un expert en forensique documentaire et détection de fraude.
Tu analyses {doc_hint} nommé "{filename}".

Examine attentivement ce document et détermine s'il est AUTHENTIQUE ou FALSIFIÉ.

Critères d'analyse :
- Cohérence visuelle (polices, alignements, logos, mise en page)
- Présence d'artefacts de manipulation (JPEG artifacts, zones floutées, incohérences de pixels)
- Cohérence des informations (dates, numéros, références)
- Qualité et style d'impression / scan
- Présence de sécurités attendues (hologrammes, filigranes, numéros de série)
- Cohérence avec les formats officiels connus de ce type de document

Réponds UNIQUEMENT avec un JSON valide (sans markdown, sans explication hors JSON) :
{{
  "verdict": "AUTHENTIQUE" | "FALSIFIÉ",
  "confidence_score": <0-100>,
  "summary": "<phrase courte expliquant le verdict>",
  "detected_type": "<type de document détecté>",
  "passport": {{
    "doc_type": "<type précis>",
    "issuer": "<émetteur ou institution>",
    "issue_date": "<date si visible, sinon null>",
    "holder": "<nom du titulaire si visible, sinon null>",
    "file_hash": "<hash fictif SHA-256 pour cet exemple>"
  }},
  "signals": [
    {{"name": "<vérification 1>", "status": "ok"|"warn"|"fail", "icon": "<emoji>"}},
    {{"name": "<vérification 2>", "status": "ok"|"warn"|"fail", "icon": "<emoji>"}},
    {{"name": "<vérification 3>", "status": "ok"|"warn"|"fail", "icon": "<emoji>"}},
    {{"name": "<vérification 4>", "status": "ok"|"warn"|"fail", "icon": "<emoji>"}},
    {{"name": "<vérification 5>", "status": "ok"|"warn"|"fail", "icon": "<emoji>"}},
    {{"name": "<vérification 6>", "status": "ok"|"warn"|"fail", "icon": "<emoji>"}}
  ]
}}"""


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.post("/analyze")
def analyze():
    file = request.files.get("file")
    doc_type = request.form.get("doc_type", "auto")

    if not file:
        return jsonify({"error": "Aucun fichier reçu"}), 400

    filename = file.filename or "document"
    file_bytes = file.read()

    # Compute real hash
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Try Claude Vision API
    try:
        content = []

        # Attach file as image or document
        mime = file.content_type or "application/octet-stream"
        b64 = base64.standard_b64encode(file_bytes).decode()

        if mime == "application/pdf":
            content.append({
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": b64}
            })
        elif mime.startswith("image/"):
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime, "data": b64}
            })
        else:
            # Fallback: send as image/jpeg
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}
            })

        content.append({
            "type": "text",
            "text": build_analysis_prompt(doc_type, filename)
        })

        api_key = ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY", "")
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 1200,
            "messages": [{"role": "user", "content": content}],
        }

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers, json=payload, timeout=45
        )
        resp.raise_for_status()
        raw = resp.json()

        text = ""
        for block in raw.get("content", []):
            if block.get("type") == "text":
                text += block["text"]

        # Parse JSON from response
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        result = json.loads(text)
        # Inject real hash
        if "passport" in result:
            result["passport"]["file_hash"] = file_hash
        return jsonify(result)

    except Exception as e:
        # Fallback: try orchestrator or return mock
        try:
            orch_resp = requests.post(
                f"{ORCH}/process",
                files={"file": (filename, file_bytes, mime)},
                data={"doc_type": doc_type},
                timeout=30
            )
            data = orch_resp.json()
            if "passport" in data:
                data["passport"]["file_hash"] = file_hash
            return jsonify(data)
        except Exception:
            pass

        # Last resort: informative error mock
        return jsonify({
            "verdict": "ERREUR",
            "confidence_score": 0,
            "summary": f"Analyse impossible : {str(e)[:120]}",
            "detected_type": doc_type,
            "passport": {
                "doc_type": doc_type,
                "issuer": "—",
                "issue_date": None,
                "holder": None,
                "file_hash": file_hash,
            },
            "signals": [
                {"name": "Connexion API Claude", "status": "fail", "icon": "🔌"},
                {"name": "Vérifiez ANTHROPIC_API_KEY", "status": "warn", "icon": "🔑"},
            ]
        }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)