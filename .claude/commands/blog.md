---
description: SEO performance of a blog/site via the GSC MCP (traffic totals + top keywords).
argument-hint: --site <site-slug> [--days 28] [--top-kw 20] [--dry-run]
allowed-tools: Bash(python3 content_writer.py audit gsc-perf:*), Read
---

Fetches a blog's SEO performance via the GSC MCP: traffic totals
(clicks, impressions, CTR, average position) + top queries over the window.

```bash
python3 content_writer.py audit gsc-perf $ARGUMENTS
```

Options: `--site`/`--site` (required, site id), `--days` (default 28),
`--top-kw` (default 20), `--dry-run` (no local JSON dump).

Automatic routing: superprof.* → gsc-remote MCP (service account fallback);
enseigna and sites outside the MCP → service account. The source used is shown
in the summary (`source: mcp` or `service_account`).

Read-only. Report a compact summary (totals + a few top queries).
