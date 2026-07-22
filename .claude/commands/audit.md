---
description: Audit of a URL - SERP (PAA, secondary keywords) or GSC/Ahrefs state.
argument-hint: serp <url> [--main-keyword K]  |  gsc-state --site <site-slug>
allowed-tools: Bash(python3 content_writer.py audit:*), Read
---

Runs a targeted audit (read-only, no side effects).

```bash
python3 content_writer.py audit $ARGUMENTS
```

Useful subcommands:

- `audit serp <url> [--main-keyword K]` - PAA, secondary keywords, SERP features.
- `audit gsc-state --site <site-slug>` - GSC SEO state of the site (keywords ranking in top-N).
- `audit ahrefs-state` - state of play via Ahrefs.

Report the result compactly (no raw dump).
