# Sources d'autorité par matière — Superprof Ressources FR

Référence chargée à la demande depuis `source-research` (site `superprof.fr-ressources`).
Tier 1 de la recherche en cascade : identifier la **matière** de l'article, puis viser en
priorité ces domaines d'autorité au tier 2 (web), au lieu de chercher à l'aveugle.

**Règles transverses (rappel, priment sur ce tableau) :**

- Jamais Wikipédia comme source : remonter à la source primaire qu'elle agrège et lier
  celle-ci. Voir `edito-refresh/references/eeat-framework.md`.
- **Deep-link spécifique, jamais la homepage** : la source citée pointe la page précise qui
  porte l'information, pas l'accueil du domaine ni une page de catégorie
  (cf. `sites/superprof.fr-ressources/prompts/site.md`, « Specific URLs ONLY »).
- Source **datée et vérifiable** (auteur/organisme identifiable) ; toute donnée chiffrée
  porte son année.
- Ce fichier donne **où chercher** (domaines), jamais une URL de page figée : ne pas
  inventer de lien précis, le trouver et le vérifier au tier 2.
- **Programmes scolaires officiels** (toutes matières) : toute affirmation sur le
  contenu d'un programme (notions d'une spécialité, œuvres au programme, programmes
  limitatifs annuels) se vérifie sur **eduscol.education.fr** / **education.gouv.fr**
  dans sa version en vigueur au moment de la rédaction — jamais de mémoire, jamais
  reprise de l'article d'origine. Ces deux domaines valent domaine d'autorité pour
  **chaque** matière scolaire, en plus des lignes du tableau.

## Socle transverse FR (toutes matières)

Domaines d'autorité valables quel que soit le sujet (repris de l'ancienne whitelist
d'`eeat-framework.md`, désormais consolidée ici) :

| Champ | Domaines |
|---|---|
| Éducation / programmes | eduscol.education.fr, education.gouv.fr |
| Orientation / vie étudiante | onisep.fr, cned.fr, etudiant.gouv.fr, service-public.fr |
| Santé (YMYL) | has-sante.fr, inserm.fr, ameli.fr, santepubliquefrance.fr |
| Finance / droit (YMYL) | economie.gouv.fr, banque-france.fr, amf-france.org, legifrance.gouv.fr |
| Sport / culture | sports.gouv.fr, culture.gouv.fr |
| Statistiques | insee.fr, oecd.org |

## Sciences (maths, physique-chimie, SVT, informatique)

| Matière | Domaines d'autorité prioritaires | Types de sources à viser | Pièges à éviter |
|---|---|---|---|
| Maths | hal.science, cnrs.fr, education.gouv.fr, eduscol.education.fr, insee.fr (stats) | revues à comité de lecture, ressources académiques, programmes officiels | sites de cours non signés, forums d'entraide |
| Physique-chimie | cnrs.fr, cea.fr, hal.science, eduscol.education.fr | publications de laboratoires, revues scientifiques | vulgarisation sans auteur, contenu marketing |
| SVT | inserm.fr, cnrs.fr, mnhn.fr, santepubliquefrance.fr, ird.fr | études, organismes de recherche, données sanitaires datées | blogs santé non crédités (YMYL), pseudo-science |
| Informatique | inria.fr, cnrs.fr, hal.science, cnil.fr (données/RGPD) | publications, documentation officielle, autorités | tutoriels anonymes, réponses de forum non sourcées |

## Langues (anglais, espagnol, allemand, latin, français langue)

| Matière | Domaines d'autorité prioritaires | Types de sources à viser | Pièges à éviter |
|---|---|---|---|
| Anglais | britannica.com (source primaire, pas agrégateur), presse de référence anglophone (bbc.com, theguardian.com), cambridge.org, oxford institutions | grammaires de référence, corpus, presse native | traducteurs automatiques comme « source », blogs de cours |
| Espagnol | rae.es (Real Academia), cervantes.es, presse hispanophone de référence | académie de la langue, institutions culturelles | fiches auto-générées, IA sans vérification |
| Allemand | duden.de, goethe.de, presse germanophone de référence | dictionnaire/institution de référence, presse native | forums, contenus non attribués |
| Latin | gallica.bnf.fr, remacle.org (textes établis), éditions critiques universitaires | textes primaires établis, apparat critique | traductions non attribuées, sites de thèmes/versions |
| Français (langue) | academie-francaise.fr, cnrtl.fr, larousse.fr (entrées signées) | dictionnaires/institution de référence, corpus | blogs d'orthographe non sourcés |

## Lettres & sciences humaines (histoire, géographie, philosophie, français lettres)

| Matière | Domaines d'autorité prioritaires | Types de sources à viser | Pièges à éviter |
|---|---|---|---|
| Histoire | archives-nationales.culture.gouv.fr, gallica.bnf.fr, retronews.fr, unesco.org, universités/historiens reconnus | archives, presse ancienne, ouvrages d'historiens | blogs perso, récits romancés sans source |
| Géographie | insee.fr, ign.fr, statistiques.developpement-durable.gouv.fr, oecd.org, geoportail.gouv.fr | données cartographiques et statistiques datées | cartes sans source, chiffres non datés |
| Philosophie | gallica.bnf.fr, cairn.info, éditions critiques universitaires | textes primaires établis, revues à comité de lecture | résumés agrégés, fiches de révision recopiées |
| Français (lettres) | gallica.bnf.fr, bnf.fr, cairn.info, éditions critiques reconnues | textes primaires, éditions savantes, revues littéraires | fiches de lecture agrégées, analyses non signées |

## Éco-droit-social (SES, droit, management, communication, arts appliqués)

| Matière | Domaines d'autorité prioritaires | Types de sources à viser | Pièges à éviter |
|---|---|---|---|
| SES | insee.fr, oecd.org, vie-publique.fr, banque-france.fr, cairn.info | données chiffrées datées, rapports officiels, revues | statistiques sans année, opinions non sourcées |
| Droit | legifrance.gouv.fr, vie-publique.fr, service-public.fr, conseil-constitutionnel.fr | textes officiels, jurisprudence, sources primaires (YMYL) | sites juridiques commerciaux, forums de conseil |
| Management | cairn.info, insee.fr, france-strategie.gouv.fr, oecd.org | revues de gestion, études, rapports | contenus de blogs d'entreprise déguisés en cours |
| Communication | cairn.info, arcom.fr, ina.fr | revues académiques, autorités du secteur, archives audiovisuelles | contenus promotionnels d'agences |
| Arts appliqués | culture.gouv.fr, centrepompidou.fr, ina.fr, musées nationaux | institutions culturelles, fonds muséaux, archives | images/analyses sans attribution ni crédit |

> Liste ouverte : ajouter une matière ou un domaine validé au fil des articles (tier 3 de
> la cascade). Un domaine cité ici doit respecter les types d'autorité transverses
> (`edito-refresh/references/eeat-framework.md`) et ne jamais figurer dans la blacklist
> (`source-research/references/blacklisted-domains.md`) — pas de forum, pas de réseau
> social, pas de Wikipédia.
