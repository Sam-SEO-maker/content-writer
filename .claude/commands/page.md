---
description: SEO performance of a specific URL via the GSC MCP (queries, clicks, impressions, position).
argument-hint: <url> [--days 28] [--dry-run]
allowed-tools: Bash(python3 content_writer.py audit gsc-page:*), Read
---

Fetches the GSC performance of a **specific page**: the queries it ranks for,
with clicks, impressions and position, over the given window.

```bash
python3 content_writer.py audit gsc-page $ARGUMENTS
```

The site is inferred automatically from the URL (no `--site` to pass).
Routing: superprof.* → gsc-remote MCP (service account fallback); the MCP
caps the display at ~20 queries.

Options: `<url>` (required), `--days` (default 28), `--dry-run` (no JSON dump).

For the performance of the **whole blog**, use `/blog --site <site-slug>`.
Read-only. Report a compact summary (traffic + main queries).
