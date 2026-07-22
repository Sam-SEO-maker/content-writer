---
description: Validates the SEO quality of a content_plan.md (heading hierarchy, PAA coverage, proofs) - deterministic, no generation.
argument-hint: <url> --site <site-slug> [--plan-file path] [--json]
allowed-tools: Bash(python3 content_writer.py plan check:*), Bash(python3 content_writer.py plan init:*), Read
---

> Plan lifecycle: `plan init` (scaffold + injected signals) → the agent fills in
> the outline via the `seo-outline` skill → **`plan check`** (this command) validates.
> `plan init` lays the file at the right path; the CLI never writes the content.

Grades the SEO quality of the editorial outline (`content_plan.md`) produced at
step 2bis of `/refresh` (`seo-outline` skill). **100% deterministic**: no
generation, no API call - the command only *checks*, never writes.

Runs:

```bash
python3 content_writer.py plan check $ARGUMENTS
```

Mechanical checks applied (invariants of the `seo-outline` skill):

- **Heading hierarchy**: ≥ 3 H2s, no orphan H2 or H3, 2-4 H3s per H2,
  subdivision required beyond 150 words, `?` on interrogative headings;
- **PAA coverage**: every PAA question from `audit_data.json` appears in the
  plan (resolved automatically from the URL's context_dir);
- **Proofs**: ≥ 3 source links and ≥ 2 numbered statistics placed.

Verdict:

- **OK** (exit 0) → the plan is sound, move on to generation (step 3 of `/refresh`);
- **NEEDS_FIX** (exit 1) → list of shortcomings; fix the plan (cheap)
  **before** writing the article, not after.

The plan is resolved from the URL (`_shared/context/<slug>/content_plan.md`); pass
`--plan-file` to point to an explicit file, `--json` for scriptable output.
