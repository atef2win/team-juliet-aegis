# AEGIS — Hackathon PSTB 2026 · Team Juliet

> **Digital Trust Hub** — vérifier l'authenticité d'un document : détection IA + sceau C2PA + ancrage blockchain + preuve QR partageable.

Ce repo est un **squelette qui tourne déjà** (mocks). Chacun remplit **son service**. On intègre dès le départ, pas à la fin.

## 🚀 Démarrer en 1 commande

```bash
git clone <url-du-repo> && cd aegis
docker compose up --build
```

Puis ouvre **http://localhost:8000** → clique « Vérifier » → tu vois le **passeport** (avec des données mock). Le pipeline complet tourne déjà. 🎉

## 🧩 Les services (1 personne = 1 dossier)

| Dossier | Owner | Rôle | Port | Endpoint |
|---|---|---|---|---|
| `services/detect` | **Mariem** | OCR + détection de fraude | 8001 | `POST /detect` |
| `services/seal` | **Romuald** | hash SHA-256 + signature C2PA | 8002 | `POST /seal` |
| `services/anchor` | **Mohamed B.Y.** | ancrage OpenTimestamps + DB | 8003 | `POST /anchor` |
| `services/verify` | **Fatma** | vérif on-chain + QR | 8004 | `GET /verify/<id>` |
| `services/ui` | **Sami** | interface upload + passeport | 8000 | `GET /` |
| `services/orchestrator` | **Atef** | enchaîne les services (= n8n en prod) | 8080 | `POST /process` |

➡️ Contrats d'entrée/sortie détaillés : [`contracts/contracts.md`](contracts/contracts.md)

## 🔧 Comment bosser sur SON service

1. Ouvre ton dossier `services/<toi>/app.py`.
2. Remplace le `# TODO` (la réponse mock) par ton vrai code.
3. **Garde le même format de sortie** (le contrat) → rien ne casse chez les autres.
4. Teste en local : `docker compose up --build <ton-service>` ou tout le stack.

## 🌿 Règles d'équipe (à distance)

- **Push souvent**, petits commits. Branche `feat/<ton-service>` → Pull Request vers `main`.
- **Ne touche que ton dossier** (sauf accord). Le reste tourne en mock tant que ce n'est pas fini.
- **Atef intègre** sur la machine de démo toutes les ~3-4h.
- Bloqué ? → poste dans **#all-aegis**. Entraide prioritaire sur `detect` (chemin critique).

## 🎯 Règle d'or

> On **intègre à H+1** (avec les mocks), pas à H+20. On **montre** la grande archi, on **démontre** la tranche fine : `detect → seal → anchor → QR`.
