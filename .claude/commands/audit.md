---
description: Audit d'une URL — SERP (PAA, secondary keywords) ou éditorial (E-E-A-T, fraîcheur, quality gate).
argument-hint: serp <url> [--keyword K]  |  editorial <url> --blog <id>
allowed-tools: Bash(python3 content_writer.py audit:*), Read
---

Lance un audit ciblé (lecture seule, sans effet de bord).

```bash
python3 content_writer.py audit $ARGUMENTS
```

Sous-commandes utiles :

- `audit serp <url> [--keyword K]` — PAA, secondary keywords, features SERP.
- `audit editorial <url> --blog <id>` — E-E-A-T, fraîcheur, quality gate
  (score < 4 bloque un refresh).
- `audit gsc-state --site <id>` — état des lieux SEO GSC (KW positionnés top-N).
- `audit ahrefs-state` — état des lieux via Ahrefs.

Rapporter le résultat de façon compacte (pas de dump brut).
