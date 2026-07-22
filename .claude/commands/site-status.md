---
description: SEO state of play of a site via GSC (keywords ranking in top-N, performance) → dedicated Sheet.
argument-hint: --site <enseigna|superprof.fr-ressources> [--months 3] [--top-pos 30] [--dry-run]
allowed-tools: Bash(python3 content_writer.py audit gsc-state:*), Read
---

Draws up the SEO state of play of a site: ranked keywords (top-N positions)
over the period, pushed to a dedicated Sheet, one tab per site.

```bash
python3 content_writer.py audit gsc-state $ARGUMENTS
```

Options: `--site` (required), `--months` (default 3), `--top-pos` (default 30),
`--min-impressions`, `--dry-run` (local dump only, no write to the Sheet).

Read-only on the content side. Report a compact summary (number of keywords kept,
position distribution).
