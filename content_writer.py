#!/usr/bin/env python3
"""
Content Writer CLI

Unified CLI for the multi-site SEO refresh workflow.

Usage:
    cw refresh <url> --site enseigna.fr
    cw refresh <url> --site superprof.fr-ressources
    cw workflow run <url> --site enseigna.fr [--row 3]
    cw audit editorial <url> --site superprof.fr-ressources
    cw batch audit-gsc --site enseigna.fr
    cw debug workflow <url> --site enseigna.fr
    cw statuts <url> "Rédigé"
"""

import sys
from pathlib import Path

# Ajouter le répertoire au path
sys.path.insert(0, str(Path(__file__).parent))

import click
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()


@click.group()
@click.version_option(version="3.0.0", prog_name="Content Writer")
@click.pass_context
def cli(ctx):
    """
    Content Writer - multi-site SEO refresh engine.

    Refreshes existing articles from data signals (GSC + DataForSEO),
    driven by Google Sheets batches. Sites live under sites/<site-slug>/,
    onboarded on demand from the ~96-site catalog (`site list` / `site init`).
    Content generation runs through the Claude Code subagent (Max plan),
    never the paid API. The Golden Rule applies to every refresh:
    never reduce the assets (images, tables, videos, links).
    """
    ctx.ensure_object(dict)


# Import des groupes de commandes
from cli.commands import refresh, audit, batch, linking
from cli.commands import ytg, notion_cmd
from cli.commands import plan as plan_cmd
from cli.commands import finalize as finalize_cmd
from cli.commands import statuts as statuts_cmd
from cli.commands import ngl_status as ngl_status_cmd
from cli.commands import site as site_cmd
from cli.commands import status_cmd

# Enregistrer les commandes
cli.add_command(refresh.refresh)
cli.add_command(finalize_cmd.finalize)
cli.add_command(audit.audit)
cli.add_command(batch.batch)
cli.add_command(linking.linking)
cli.add_command(ytg.ytg)
cli.add_command(plan_cmd.plan)
cli.add_command(notion_cmd.notion)
cli.add_command(statuts_cmd.statuts)
cli.add_command(status_cmd.status)
cli.add_command(ngl_status_cmd.ngl_status)
cli.add_command(site_cmd.site)


if __name__ == "__main__":
    cli()
