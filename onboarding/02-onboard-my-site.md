# 02 — Onboard my site

Goal: create your site's folder — `sites/<site-slug>/`, where `<site-slug>` is your
**`site_slug`** from the catalog (e.g. `superprof.com`) — then fill it in. Everything
you write goes into one of three places inside that folder:

- **`config/site.json`** — your site's settings: WordPress login names, SEO targets,
  Google Sheet ids (steps 3–4). You don't need to know JSON: you'll ask **Claude**
  to fill it — you bring the information, it
  writes the file.
- **`prompts/site.md`** — your editorial rules in plain text: tone, do's and don'ts,
  formatting specifics (step 5).
- **`.claude/skills/<your-skill-name>/`** — your writing skill: how an article for
  your country should be structured and written (step 6).

The steps below walk you through each one in order.

> Prerequisite: you've finished [01 — Set up your machine](01-setup-machine.md) and
> `python3 content_writer.py --help` works.

## 1. Find your site id

```bash
python3 content_writer.py site list
```

This prints the catalog. The value you want is the **`site_slug`** column — that string
*is* your `<site-slug>` everywhere in these guides. The slug is **your site's domain as
you type it** (e.g. `superprof.mx`, `superprof.ae`). When one domain hosts both a blog
and a ressources site, the ressources slug appends its real URL segment
(e.g. `superprof.es-apuntes`, `superprof.de-lernplattform`). A `[x]` means the site is
already onboarded.

## 2. Scaffold your site

```bash
python3 content_writer.py site init <site-slug>
```

This does three things:
1. Creates `sites/<site-slug>/` with `config/`, `prompts/`, `linking_maps/`, `outputs/`.
   (Your writing-skill folder `.claude/skills/` is **not** created here — you'll add it
   yourself in step 6. That's expected.)
2. Writes a **minimal** `config/site.json` — only the identity fields it can derive
   from the catalog (`site_slug`, `display_name`, `domain`, `url_base`, `gsc_property`,
   `language`, plus safe defaults for `auth_mode`/`content_type`) — and a `_TODO` line
   listing everything **you** must still add by hand (tone_profile, seo_settings,
   wp_api_config, sheets, …). It is a **skeleton, not a finished config**: expect ~12
   lines, not the rich hundred-line file a mature site ends up with. You'll flesh it
   out in steps 3–4, using the model files in
   [`site-model/`](site-model/README.md) as your starting point (that folder is on
   your disk; the reference site `superprof.fr-ressources` is **not**).
3. Adds your folder to the sparse-checkout (so it shows up in your working tree) and
   registers your site in `_shared/config/sites.json`.

## 3. Connect your WordPress login

Your site now exists, so you can set up the WordPress credentials for your blog. They
live in **two files you connect together** — this is the step people find fiddly.

**The easy way: ask Claude.** Open the Claude Code panel in VS Code and say:

> Add the `wp_api_config` block to `sites/<site-slug>/config/site.json`, following
> step 3 of `onboarding/02-onboard-my-site.md`.

Claude derives every value from your site and writes the block for you. Then do
**part b yourself** (it involves your password — see the 🔒 rule below).

The rest of this step explains what Claude is doing, so you can check its work —
read it once, you don't have to build the block by hand.

**a. Add the `wp_api_config` block to your site config.** The block goes in
`sites/<site-slug>/config/site.json` (in VS Code: `Cmd/Ctrl+P`, then type
`site.json`). `site init` did **not** create this block. Every value
is derived from **your own** site, from the `gsc_property` already in the file, with
these three rules:

- **`api_base_url`** = your `gsc_property` + `wp-json/wp/v2`.
  If `gsc_property` is `https://www.superprof.it/blog/`, then
  `api_base_url` is `https://www.superprof.it/blog/wp-json/wp/v2`.
- **`user_env_var`** / **`password_env_var`** = `WP_<SITE>_USER` /
  `WP_<SITE>_APP_PASSWORD`, where `<SITE>` is your `site_slug` upper-cased with `.`
  and `-` turned into `_`. For `superprof.it` → `WP_SUPERPROF_IT_USER` /
  `WP_SUPERPROF_IT_APP_PASSWORD`. (Pick any consistent name — it just has to match
  `.env` in part b; the slug-based convention keeps it unambiguous.)

So a `superprof.it` blog gets:

```jsonc
"wp_api_config": {
  "api_base_url": "https://www.superprof.it/blog/wp-json/wp/v2",
  "user_env_var": "WP_SUPERPROF_IT_USER",
  "password_env_var": "WP_SUPERPROF_IT_APP_PASSWORD",
  "timeout": 30
}
```

Careful: `user_env_var` and `password_env_var` do **not** contain your login and
password. They only hold **labels** — like the name written on a mailbox. Your real
login and password go into another file, `.env` (part b), under those exact labels.
`site.json` writes the name on the mailbox; `.env` puts the contents inside. That's
why this file is safe to commit while `.env` never is.

**b. Put the real values in `.env`.** Ask the **tech team** for your blog's WordPress
login and *Application Password*. Then open the `.env` you created in
[01 — step 7](01-setup-machine.md) and add exactly the two names you wrote in part a, with
the values they gave you (continuing the `superprof.it` example):

```bash
WP_SUPERPROF_IT_USER=your-wp-login
WP_SUPERPROF_IT_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

The two labels in `.env` must match the ones you wrote in `site.json`
(`user_env_var` and `password_env_var`) **character for character** — that label is
the only link between the two files. Fill in **only** your blog's two lines.

> 🔒 Your Application Password goes **only** into `.env` — never pasted into the Claude
> Code chat. You can ask Claude to write the line into `.env` for you; just don't show it
> the value in the conversation. (Same golden rule as [01 — step 7](01-setup-machine.md).)

## 4. Complete the rest of your `site.json`

Back in `sites/<site-slug>/config/site.json`, the remaining `_TODO` values need your
input. Same method as step 3: **tell Claude the information and let it write the
JSON**. For example:

> In my `site.json`, fill in `tone_profile` (friendly, informal "tu", for students),
> `sheets` (my Google Sheet id is …), and set `generation_skill` to `<my-skill-name>`.

What each field means:

- `tone_profile` — voice and register for your site.
- `seo_settings` — your SEO thresholds/targets.
- `sheets` — your Google Sheet id(s), if you drive refreshes from a sheet.
- `generation_skill` / `qc_skill` — the name of the writing/QC skills you'll create
  in step 6 (this is how the generator finds them; it is **not** hardcoded).

Want to see what a finished config looks like? Open
**[`site-model/config/site.model.json`](site-model/config/site.model.json)**
(explained field by field in **[site-model/](site-model/README.md)**).

## 5. Write your `site.md`

`sites/<site-slug>/prompts/site.md` is the master editorial source for your site:
tone, blacklist, WordPress format specifics. The scaffold left a placeholder — replace
it. Copy the skeleton from
[`site-model/prompts/site.model.md`](site-model/prompts/site.model.md) and rewrite
each section for your language and country.

Drop any extra editorial material (guides, block examples) under
`sites/<site-slug>/prompts/`.

## 6. Install your writing skill

Your site's writing rules live in a **skill scoped to your site**. This folder
doesn't exist yet (the scaffold didn't create it) — **you create it now**, at:

```
sites/<site-slug>/.claude/skills/<your-skill-name>/SKILL.md
```

**Write it your way** — this skill is where *your* SEO and editorial expertise for your
site's country lives, and you know that country better than anyone. There's no house template to
replicate: the writing rules, structure, and tone are yours to decide.

The only hard requirements are technical, so the engine can find and run your skill:

- It lives at `sites/<site-slug>/.claude/skills/<your-skill-name>/SKILL.md`.
- Its front-matter has a `name:` and a `description:` (the `description` is what tells the
  engine when to use it — write it well).
- Your `site.json` `generation_skill` (and optionally `qc_skill` (quality_check)) points at that exact
  `name:`.

If you'd like a concrete starting point, [`site-model/skill/SKILL.model.md`](site-model/skill/SKILL.model.md)
shows the front-matter shape and the kinds of sections a skill can have — treat it as a
blank canvas, not a pattern to copy. Want to see a fully worked example? Ask the
maintainer.

> **What's already on your machine vs what you create.** The **cross-cutting** skills
> (`edito-refresh`, `format-wordpress`, `recherche-sources`) and the **slash commands**
> (`/refresh`, `/audit`, `/batch`, …) live at the repo root under `.claude/`, which is
> part of the shared engine — they're already on your disk and working, **you don't
> install or recreate them**. The only skill you create is **your own** writing (and
> optional QC) skill under `sites/<site-slug>/.claude/skills/`. You never see other
> sites' skills (e.g. `superprof.fr-ressources`'s) because their site folders aren't on
> your disk — and you don't need them.

## 7. Ask for your CODEOWNERS line

The `.github/` folder is locked to the maintainer, so you can't add yourself. Ask
**@Sam-SEO-maker** to add your ownership line:

```
/sites/<site-slug>/   @Sam-SEO-maker @your-github-handle
```

This makes you the required reviewer for your own site.

## 8. Send your site for review

Your site folder only exists on your computer so far. This last step sends it to the
shared repository, where the maintainer reviews and approves it. You don't need to
know git — ask Claude:

> Send my new site folder `sites/<site-slug>` for review, following step 8 of
> `onboarding/02-onboard-my-site.md`: branch `onboard/<site-slug>`, commit only
> `sites/<site-slug>`, commit message `feat(site): onboard <site-slug>`, then open
> the pull request.

Claude runs the git commands and gives you a link to the review page. Tell the
maintainer it's ready — once they approve, your site is officially part of the repo.

## Done

Your site is live locally and reviewable. Next: **[03 — Daily usage](03-daily-usage.md)**.
