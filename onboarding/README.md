# Onboarding — Content Writer (Superprof SEO)

Welcome! This repo is the **multi-site SEO refresh agent** created for Superprof blogs. Every country blog is a **site** (a folder under `sites/`). You are the
SEO Manager for one country (ES, UK, US, MX, ID, JP, …) and you work on **your site only**.

## How this works in one picture

- **One shared repo.** Everyone clones the same repository.
- **You only see your own site.** The setup script copies to your computer the
  shared engine and **your single `sites/{site-slug}/` folder**. The other sites
  stay on GitHub and never appear on your disk — no clutter, no risk of touching
  someone else's site.
- **Please, do not change anything in the engine.** You might not have to modify anything outside your site folder
  (`_shared/`, `cli/`, `scripts/`, `content_writer.py`, …).
  In practice: work only inside `sites/{site-slug}/`, and if you think the engine
  needs a change, ask the maintainer.

## Your path (do these in order)

1. **[01 — Set up your machine](01-setup-machine.md)** — install VS Code, Python, clone
   the repo (sparse), create the virtual environment, configure `.env` and credentials.
2. **[02 — Onboard my site](02-onboard-my-site.md)** — create your site folder,
   fill in its config, write your `site.md`, install your writing skill.
3. **[03 — Daily usage](03-daily-usage.md)** — the architecture, the slash commands and
   CLI, and the end-to-end refresh workflow.

Reference model to copy from: **[site-model/](site-model/README.md)**.

## Need help?

Anything about the **engine** (`_shared/`, `cli/`, `scripts/`, `.github/`), a new
credential, or your **CODEOWNERS** line → ask Samuel(**@Sam-SEO-maker**).
Everything inside `sites/{site-slug}/` is yours to change and ship via a pull request.
