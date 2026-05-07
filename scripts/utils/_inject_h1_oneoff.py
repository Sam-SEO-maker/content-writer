"""
One-off : injecte le champ `h1` dans les 31 metadata.json existants
qui ne l'ont pas encore (Superprof + Enseigna).

H1 rédigés à la main : reformulation éditoriale du title (angle complémentaire).
Stratégie : title = focus mot-clé/CTA, h1 = angle pédagogique/exhaustif.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUP = REPO_ROOT / "_shared/outputs/superprof-ressources/metadata"
ENS = REPO_ROOT / "_shared/outputs/enseigna/metadata"

H1_MAP = {
    SUP / "https_www_superprof_fr_ressources_allemand_allemand_6eme_connaissance_conjugaison_allemand_html_metadata.json":
        "Verbes au présent et pronoms personnels en allemand pour bien démarrer la 6ème",
    SUP / "https_www_superprof_fr_ressources_allemand_allemand_6eme_habitat_conjugaison_germanique_html_metadata.json":
        "Trois verbes pour dire « habiter » en allemand : nuances, conjugaison et erreurs à éviter",
    SUP / "https_www_superprof_fr_ressources_allemand_allemand_tous_niveaux_goethe_poesie_html_metadata.json":
        "À la découverte de Goethe : ses plus beaux poèmes, leur analyse et leur portée littéraire",
    SUP / "https_www_superprof_fr_ressources_allemand_allemand_tous_niveaux_mots_france_allemagne_html_metadata.json":
        "Gallicismes, germanismes et faux amis : ces mots qui voyagent entre français et allemand",
    SUP / "https_www_superprof_fr_ressources_allemand_allemand_tous_niveaux_vocabulaire_francophone_germanique_html_metadata.json":
        "Comment choisir et utiliser un bon dictionnaire français-allemand selon ton niveau",
    SUP / "https_www_superprof_fr_ressources_allemand_allemand_tous_niveaux_vocabulaire_langue_goethe_html_metadata.json":
        "Liste alphabétique de mots allemands commençant par L : sens, genre et contexte d'usage",
    SUP / "https_www_superprof_fr_ressources_anglais_anglais_6eme_prononciation_transparence_prononciation_signification_html_metadata.json":
        "Reconnaître et bien prononcer les mots transparents anglais en classe de 6ème",
    SUP / "https_www_superprof_fr_ressources_arts_appliques_arts_appliques_1ere_commencer_le_dessin_html_metadata.json":
        "Premiers pas en dessin pour la 1ère arts appliqués : matériel, techniques et exercices",
    SUP / "https_www_superprof_fr_ressources_espagnol_espagnol_2nde_explication_document_hispanique_html_metadata.json":
        "Méthode pas à pas pour analyser un document hispanique en cours d'espagnol de seconde",
    SUP / "https_www_superprof_fr_ressources_geographie_geographie_3eme_espaces_japonais_html_metadata.json":
        "Mégalopole, façades maritimes et défis : les espaces du Japon expliqués pour le brevet",
    SUP / "https_www_superprof_fr_ressources_geographie_geographie_tous_niveaux_analyse_territoire_allemagne_geo_html_metadata.json":
        "Le territoire allemand vu de près : organisation fédérale, démographie et grandes régions",
    SUP / "https_www_superprof_fr_ressources_geographie_geographie_tous_niveaux_les_boliviens_et_leur_pays_html_metadata.json":
        "Découvrir la Bolivie : un pays andin entre montagnes, peuples autochtones et richesses naturelles",
    SUP / "https_www_superprof_fr_ressources_geographie_geographie_tous_niveaux_revolution_francaise_assemblees_html_metadata.json":
        "Constituante, Législative, Convention : les cinq assemblées qui ont fait la Révolution française",
    SUP / "https_www_superprof_fr_ressources_geographie_geographie_tous_niveaux_verdure_ville_antique_merveille_mondiale_html_metadata.json":
        "Les jardins suspendus de Babylone : entre légende et réalité d'une merveille disparue",
    SUP / "https_www_superprof_fr_ressources_histoire_histoire_2nde_cite_grecque_citoyennete_html_metadata.json":
        "Vivre en citoyen dans l'Athènes du Vème siècle : démocratie, droits et institutions",
    SUP / "https_www_superprof_fr_ressources_histoire_histoire_5eme_arabes_peuple_religion_html_metadata.json":
        "L'essor de la civilisation arabo-musulmane au Moyen Âge : naissance de l'islam, califats et grandes villes",
    SUP / "https_www_superprof_fr_ressources_histoire_histoire_terminale_s_colonies_europeennes_trente_html_metadata.json":
        "La colonisation européenne et ses héritages : faire le bilan pour le bac de Terminale",
    SUP / "https_www_superprof_fr_ressources_maths_maths_3eme_bucheron_noix_saveurs_html_metadata.json":
        "Mise en équation et fractions : la stratégie pour démêler le problème du bûcheron en 3ème",
    SUP / "https_www_superprof_fr_ressources_maths_maths_3eme_diviseurs_commun_nombres_html_metadata.json":
        "PGCD et algorithme d'Euclide : trouver les diviseurs communs de deux nombres en 3ème",
    SUP / "https_www_superprof_fr_ressources_maths_maths_4eme_biographie_scientifique_turquie_html_metadata.json":
        "Cahit Arf, mathématicien turc : son parcours et son apport à l'algèbre expliqués aux 4e",
    SUP / "https_www_superprof_fr_ressources_maths_maths_4eme_fiche_rappel_calcul_html_metadata.json":
        "Toutes les règles de calcul à maîtriser en 4e : relatifs, fractions, puissances et calcul littéral",
    SUP / "https_www_superprof_fr_ressources_maths_maths_4eme_positif_negatif_autre_html_metadata.json":
        "Déterminer le signe d'un produit avec la règle des signes : méthode pour la 4e",
    SUP / "https_www_superprof_fr_ressources_maths_maths_tous_niveaux_methode_graphique_tracage_html_metadata.json":
        "Comment tracer une courbe avec rigueur : méthode graphique étape par étape",
    SUP / "https_www_superprof_fr_ressources_physique_chimie_physique_chimie_2nde_protons_noyau_atome_html_metadata.json":
        "De l'atome aux ions : comprendre les éléments chimiques qui composent l'univers",
    SUP / "https_www_superprof_fr_ressources_ses_ses_2nde_changements_histoire_familles_html_metadata.json":
        "L'évolution de la famille en France : du modèle nucléaire aux familles recomposées en SES 2nde",
    SUP / "https_www_superprof_fr_ressources_ses_ses_terminale_es_classes_sociales_economiques_html_metadata.json":
        "Marx, Weber, Bourdieu : les classes sociales en Terminale ES expliquées pour le bac",
    SUP / "https_www_superprof_fr_ressources_ses_ses_terminale_es_evolution_economie_sociale_html_metadata.json":
        "Croissance, développement et changement social : les indicateurs clés en Terminale ES",
    SUP / "https_www_superprof_fr_ressources_svt_svt_2nde_composer_epiderme_organe_html_metadata.json":
        "De la cellule à l'organe : comment l'épiderme s'organise au microscope en SVT 2nde",
    SUP / "https_www_superprof_fr_ressources_svt_svt_5eme_marche_respiration_organes_html_metadata.json":
        "Effort physique, respiration et fonctionnement des organes : le cours de SVT 5e en pratique",
    SUP / "https_www_superprof_fr_ressources_technologie_technologie_tous_niveaux_utilisation_produit_html_metadata.json":
        "Comprendre la fonction d'usage d'un produit : définition, méthode et exemples concrets",
    ENS / "preply-avis_metadata.json":
        "Preply à l'épreuve : notre test complet, du tarif à la qualité des tuteurs en 2026",
}


def main() -> int:
    updated = 0
    for path, h1 in H1_MAP.items():
        if not path.exists():
            print(f"⚠ MISSING : {path.name}")
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        if d.get("h1"):
            print(f"⏭  ALREADY HAS h1 : {path.name}")
            continue
        d["h1"] = h1
        path.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        updated += 1
        print(f"✓ {path.name}")
    print(f"\n{updated}/{len(H1_MAP)} fichiers mis à jour")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
