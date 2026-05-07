"""
Commande statuts — met à jour le statut éditorial d'une URL dans la feuille Growing.

Usage:
    cw statuts <url> <statuts>

Valeurs valides :
    "A faire"    URL non encore traitée (valeur par défaut)
    "Rédigé"     Contenu refreshé généré
    "Draft in WP" Contenu envoyé sur WordPress (draft)
    "Publié"     Article publié

Exemples :
    cw statuts https://www.superprof.fr/ressources/maths/... "Rédigé"
    cw statuts https://www.superprof.fr/ressources/maths/... "Draft in WP"
"""

import click
from scripts.audit.superprof_gsc_audit import (
    STATUTS_VALUES,
    _build_clients,
    find_growing_row_by_url,
    write_growing_statuts,
)


@click.command()
@click.argument("url")
@click.argument("statuts_value", metavar="STATUTS")
def statuts(url, statuts_value):
    """Met à jour le statut éditorial d'une URL dans la feuille Growing (Superprof Ressources).

    STATUTS : A faire | Rédigé | Draft in WP | Publié
    """
    if statuts_value not in STATUTS_VALUES:
        click.echo(
            f"[ERREUR] Valeur invalide : '{statuts_value}'\n"
            f"Valeurs acceptées : {', '.join(STATUTS_VALUES)}",
            err=True,
        )
        raise SystemExit(1)

    sheets, _ = _build_clients()

    row_index = find_growing_row_by_url(sheets, url)
    if row_index is None:
        click.echo(f"[ERREUR] URL introuvable dans Growing : {url}", err=True)
        raise SystemExit(1)

    write_growing_statuts(sheets, row_index, statuts_value)
    click.echo(f"[OK] Ligne {row_index} → statuts = \"{statuts_value}\"")
    click.echo(f"     {url[:90]}")
