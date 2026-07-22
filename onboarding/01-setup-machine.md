# 01 — Set up your machine

Goal: get a working copy of Content Writer on your computer that contains **only your
site**, with Python ready to run. No prior developer experience required — follow the
steps in order.

## 1. Prerequisites

- A **GitHub account** with access to the `content-writer` repository. Ask the
  maintainer (**@Sam-SEO-maker**) to invite you if you can't see it.
- Admin rights to install software on your machine.

## 2. Install VS Code

Download and install **Visual Studio Code**: https://code.visualstudio.com/
It's the editor you'll use to open the project and run commands in its built-in terminal.

## 3. Install the Claude Code extension and sign in

Content Writer runs **inside Claude Code** — every article is written by a Claude Code
subagent.

1. In VS Code, open the **Extensions** panel (left sidebar, or `Cmd/Ctrl+Shift+X`),
   search for **Claude Code** (publisher **Anthropic**) and click **Install**.
2. Open Claude Code (the Claude icon in the sidebar) and **sign in**.
3. **Sign in with `superteamseo@gmail.com`** — All generation runs on this Max plan; **we never use the paid API.**

> If you sign in with a different account, generation will fall back to the paid API or
> fail. Use `superteamseo@gmail.com`.

## 4. Install Python 3 and git

You need **Python 3.10+** and **git**.

- **macOS**: install [Homebrew](https://brew.sh/), then in the Terminal:
  `brew install python git`
- **Windows**: install Python from https://www.python.org/downloads/ (tick
  *"Add Python to PATH"* during setup) and [Git for Windows](https://git-scm.com/download/win).

Check they work (in VS Code's terminal, menu *Terminal → New Terminal*):

```bash
python3 --version   # → Python 3.10 or higher
git --version
```

## 5. Clone the repo — your site only (sparse-checkout)

**Do not clone the whole repo.** Use the onboarding script so your disk only holds the
shared engine plus your site. From an empty folder where you keep your projects:

```bash
# Get the script (one-off download), then run it with your site id:
curl -fsSL https://raw.githubusercontent.com/Sam-SEO-maker/content-writer/main/onboarding/scripts/setup_sparse.sh -o setup_sparse.sh
bash setup_sparse.sh <site-slug>
cd content-writer
```

This clones the repo, enables sparse-checkout, and materialises the engine +
`sites/<site-slug>/`. The other sites are never written to your disk. Open this
`content-writer` folder in VS Code (*File → Open Folder*).

> If your site folder doesn't exist yet, that's expected — you'll create it in
> [02 — Onboard my site](02-onboard-my-site.md). The engine is enough to continue.

## 6. Create the Python environment and install dependencies

In VS Code's terminal, inside the `content-writer` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Confirm the tool runs:

```bash
python3 content_writer.py --help
python3 content_writer.py site list   # shows every site; [x] = already onboarded
```

## 7. Configure the shared credentials (`.env`)

`.env` is the private file that holds your secrets (passwords, API logins). It doesn't
exist yet — you **create** it by copying the provided template `.env.example`, which
lists every variable with empty/placeholder values as a guide. You'll fill the **shared**
credentials now; your blog's WordPress credentials come later in step 02, once your site
exists (there's nothing to fill for them yet).

```bash
cp .env.example .env   # creates .env from the template; open .env.example first if you
                       # want to see the full list of variables and what they're for
```

> 🔒 **Golden rule for every credential.** A password or API login goes **only** into the
> `.env` file — **never** typed or pasted into the Claude Code chat. If Claude asks for a
> credential, the right answer is *"it's in `.env`"*, not the value itself. `.env` is
> git-ignored, so it never leaves your machine; the chat is not a safe place for secrets.
> You can even ask Claude Code to *create or edit `.env` for you* — just tell it the
> variable name and that the value is your WP password, and let it write the file rather
> than showing the secret back in the conversation.

Now open the new `.env` in VS Code (`Cmd/Ctrl+P`, type `.env`) and set:

- **DataForSEO** (`DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`) — **shared account**,
  ask Sam if values needed. Paste them and you're done.
- **Google Search Console** — **nothing to do.** GSC data for `superprof.*` properties
  comes through the **shared Superprof MCP server** (`gsc-remote`, already declared in
  [`.mcp.json`](../.mcp.json)); Claude Code starts it automatically and the
  authentication lives on the server side. No file, no Google credential.

That's all for now. **Your blog's WordPress login is set up in
[02 — Onboard my site](02-onboard-my-site.md)**, right after your site is created —
you can't do it before then, so don't look for it here.

`.env` is git-ignored — it stays on your machine and is never shared.

## You're set up

Your machine now has the engine + your site, Python ready, and the shared credentials
in place. Next: **[02 — Onboard my site](02-onboard-my-site.md)** — you'll create
your site and finish its WordPress credentials there.
