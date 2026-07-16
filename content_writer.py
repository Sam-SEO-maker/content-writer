#!/usr/bin/env python3
"""
Content Writer CLI

CLI unifié pour le workflow de refresh SEO (Enseigna + Superprof Ressources FR).

Usage:
    cw refresh <url> --blog enseigna
    cw refresh <url> --blog superprof-ressources
    cw workflow run <url> --blog enseigna [--row 3]
    cw audit editorial <url> --blog superprof-ressources
    cw batch audit-gsc --blog enseigna
    cw debug workflow <url> --blog enseigna
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
    Content Writer - CLI unifié pour le refresh SEO

    Agent autonome de rafraîchissement de contenus SEO pour Enseigna
    et Superprof Ressources FR. Piloté par Google Sheets avec
    détection de cannibalisation, audit qualité, et mode Ghostwriter.
    """
    ctx.ensure_object(dict)


# Import des groupes de commandes
from cli.commands import refresh, workflow, audit, batch, indexing, debug, linking
from cli.commands import ytg, notion_cmd
from cli.commands import finalize as finalize_cmd
from cli.commands import statuts as statuts_cmd
from cli.commands import ngl_status as ngl_status_cmd
from cli.commands import tenant as tenant_cmd

# Enregistrer les commandes
cli.add_command(refresh.refresh)
cli.add_command(finalize_cmd.finalize)
cli.add_command(workflow.workflow)
cli.add_command(audit.audit)
cli.add_command(batch.batch)
cli.add_command(indexing.indexing)
cli.add_command(debug.debug)
cli.add_command(linking.linking)
cli.add_command(ytg.ytg)
cli.add_command(notion_cmd.notion)
cli.add_command(statuts_cmd.statuts)
cli.add_command(ngl_status_cmd.ngl_status)
cli.add_command(tenant_cmd.tenant)


if __name__ == "__main__":
    cli()
