# Contrats des services AEGIS

> **Règle :** tu peux changer ce qu'il y a DANS ton service, mais **pas le format de sortie**. C'est ce qui permet de bosser en parallèle sans se bloquer.

---

## `detect` — Mariem (port 8001)
**`POST /detect`** — entrée : `multipart/form-data` avec un champ `file` (le document).

Sortie :
```json
{
  "verdict": "authentic",            // "authentic" | "suspicious" | "fake"
  "score": 0.97,                     // 0.0 à 1.0
  "signaux": ["aucune anomalie"],    // liste des signaux détectés
  "explication": "texte lisible"     // justification (idéal : généré par LLM)
}
```

## `seal` — Romuald (port 8002)
**`POST /seal`** — entrée : `file` + champ `meta` (JSON string, optionnel).

Sortie :
```json
{
  "hash": "sha256...",
  "signature": "...",
  "fichier_signe": "url ou chemin",
  "did": "did:key:..."
}
```

## `anchor` — Mohamed B.Y. (port 8003)
**`POST /anchor`** — entrée JSON : `{ "hash": "sha256..." }`.

Sortie :
```json
{
  "preuve_ots": "url ou chemin .ots",
  "horodatage": "2026-06-25T12:00:00Z",
  "reseau": "bitcoin"
}
```

## `verify` — Fatma (port 8004)
**`GET /verify/<id>`** — retrouve la preuve et la vérifie.

Sortie :
```json
{
  "id": "abc123",
  "statut": "authentique",           // "authentique" | "falsifie" | "inconnu"
  "preuve_onchain": "...",
  "verifie_le": "2026-06-25T12:00:00Z"
}
```

## `orchestrator` — Atef (port 8080)
**`POST /process`** — enchaîne `detect → seal → anchor`, stocke, renvoie le passeport.
> En production, ce rôle est tenu par **n8n**. L'orchestrator local sert au dev/démo hors-ligne.

Sortie :
```json
{
  "id": "abc123",
  "detection": { ... },
  "seal": { ... },
  "anchor": { ... },
  "passeport": "/verify/abc123"
}
```
