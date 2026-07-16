#!/usr/bin/env python3
"""Hook Stop : rappelle de mettre à jour CLAUDE.md / README.md quand un module,
une commande ou une skill a changé sans que la doc suive.

Non-bloquant : émet un simple rappel (exit 0 + message) si le diff de travail
touche une surface « publique » (commandes, skills, modules CLI) mais PAS les
fichiers de doc d'orientation. Aucun faux positif gênant : un diff qui ne touche
que du code interne, des tests ou de la doc ne déclenche rien.

Surfaces surveillées (ajout OU modification) :
  - .claude/commands/*.md        (slash commands)
  - .claude/skills/**            (skills transverses)
  - tenants/*/.claude/skills/**  (skills tenant)
  - cli/commands/*.py            (groupes/commandes CLI)

Docs attendues en regard : CLAUDE.md, README.md (l'une des deux suffit).

Le hook lit le diff via git (working tree + staged) ; s'il n'est pas dans un
repo git ou si git est indisponible, il ne dit rien (exit 0 silencieux).

Sortie : émet un JSON `{"systemMessage": ...}` sur stdout (affiché à l'utilisateur
par la harness) quand un rappel est nécessaire ; rien sinon. Toujours exit 0.
"""
import json
import subprocess
import sys

WATCHED_PREFIXES = (
    ".claude/commands/",
    ".claude/skills/",
    "cli/commands/",
)
DOC_FILES = {"CLAUDE.md", "README.md"}


def _changed_files() -> set[str]:
    """Fichiers modifiés/ajoutés dans le working tree + index (git)."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if out.returncode != 0:
        return set()
    files: set[str] = set()
    for line in out.stdout.splitlines():
        # format porcelain: "XY <path>" (ou "XY <old> -> <new>" pour les renames)
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            files.add(path)
    return files


def _is_watched(path: str) -> bool:
    if path.startswith(WATCHED_PREFIXES):
        return True
    # skills scopées par tenant : tenants/<id>/.claude/skills/...
    if path.startswith("tenants/") and "/.claude/skills/" in path:
        return True
    return False


def main() -> int:
    changed = _changed_files()
    if not changed:
        return 0

    watched = sorted(p for p in changed if _is_watched(p))
    if not watched:
        return 0

    docs_touched = {p for p in changed if p in DOC_FILES}
    if docs_touched:
        return 0  # la doc suit déjà, rien à signaler

    msg = (
        "📝 Rappel doc : ces changements touchent une surface publique "
        "(commandes / skills / CLI) sans mise à jour de CLAUDE.md ni README.md :\n"
        + "\n".join(f"   - {p}" for p in watched)
        + "\n   → Reflète l'ajout/modif dans l'index CLAUDE.md (et README.md si pertinent)."
    )
    print(json.dumps({"systemMessage": msg}))
    return 0  # non-bloquant


if __name__ == "__main__":
    sys.exit(main())
