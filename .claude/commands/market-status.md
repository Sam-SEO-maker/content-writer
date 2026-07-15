---
description: État des lieux SEO d'un marché/blog via GSC (KW positionnés top-N, perfs) → Sheet dédiée.
argument-hint: --site <enseigna|superprof-ressources> [--months 3] [--top-pos 30] [--dry-run]
allowed-tools: Bash(python3 content_writer.py audit gsc-state:*), Read
---

Dresse l'état des lieux SEO d'un tenant : mots-clés positionnés (top-N positions)
sur la période, poussés dans une Sheet dédiée par onglet.

```bash
python3 content_writer.py audit gsc-state $ARGUMENTS
```

Options : `--site` (requis), `--months` (défaut 3), `--top-pos` (défaut 30),
`--min-impressions`, `--dry-run` (dump local seulement, sans écrire au Sheet).

Lecture seule côté contenu. Rapporter un résumé compact (nombre de KW retenus,
répartition des positions).
