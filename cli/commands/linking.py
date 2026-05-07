"""
Commandes de maillage interne automatisé.

Pour injecter du linking interne, utiliser directement `LinkInjector`
avec un mapping CSV manuel (voir `_shared/config/linking_maps/`).
"""

import click


@click.group()
def linking():
    """Maillage interne automatisé."""
    pass


@linking.command()
def preview():
    """Prévisualise les injections de liens à partir d'un mapping CSV."""
    click.echo(
        "Utilisez LinkInjector avec un mapping CSV dans _shared/config/linking_maps/."
    )


@linking.command()
def run():
    """Injecte les liens internes à partir d'un mapping CSV."""
    click.echo(
        "Utilisez LinkInjector avec un mapping CSV dans _shared/config/linking_maps/."
    )
