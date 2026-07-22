---
description: Runs the decision engine (data-driven GSC/DataForSEO) on a blog's URLs from Google Sheets.
argument-hint: --site <site-slug> [--spreadsheet-id ID]
allowed-tools: Bash(python3 content_writer.py batch decision:*), Read
---

Runs the decision engine in batch: for each URL of the blog, computes the
strategic action (TITLE_OPTIMIZATION / PARTIAL_REFRESH / FULL_REFRESH /
EEAT_REWRITE / NO_ACTION…) from GSC + DataForSEO signals.

```bash
python3 content_writer.py batch decision $ARGUMENTS
```

Reads and writes the decision column in the Sheet. Triggers no
generation: this is step 5 of the workflow (decision), upstream of the refresh.

Report the distribution of actions decided by the engine.
