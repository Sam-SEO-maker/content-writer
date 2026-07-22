# Connaissance pays — France (fr-FR)

Couche de **connaissance marché** pour le contenu français : système éducatif,
vocabulaire opérationnel, phrasés validés (crédit d'impôt), sources et références
culturelles préférées. Importée du paquet `blog-refresh.skill` (équipe SEO/Éditorial
Superprof, juillet 2026) et adaptée au pipeline Content Writer.

À charger **au besoin** pendant la rédaction/le refresh d'un article FR. La mécanique
typographique française (NBSP, guillemets, casse, connecteurs IA) vit dans
`.claude/skills/format-wordpress/references/typographie-fr.md` ; le ton et la
structure restent régis par `prompts/site.md` du site.

---

## 1. Formats — monnaie, nombres, dates

| Élément | Format | Exemple |
|---|---|---|
| Monnaie | `montant⎵€` (NBSP avant €) | `30 €`, `1 250 €` |
| Décimale | virgule | `12,5 €` |
| Milliers | espace insécable | `1 234 567` |
| Pourcentage | `nombre⎵%` (NBSP avant %) | `72,2 %` |
| Date longue (corps de texte) | `le 15 mars 2026` | préférée |
| Date courte | `15/03/2026` | JJ/MM/AAAA |
| Heure | `14h30` | convention française |
| Téléphone | `01 23 45 67 89` | espaces par paires |

Mécanique complète (NBSP, guillemets, italiques) → `typographie-fr.md`.

## 2. Adresse au lecteur & profils d'audience

L'adresse est fixée par le **site** (Superprof Ressources : **tutoiement**, cf.
`site.md`). Ces profils servent à régler le ton à l'intérieur de ce cadre :

| Profil | Articles typiques | Ton |
|---|---|---|
| **Lycéens** (15-18) | Bac, oraux, matières | Chaleureux, encourageant, exemples concrets, pas de jargon intimidant |
| **Collégiens** (11-14) | Brevet, méthodes | Structure simple, paragraphes courts |
| **Parents** | Soutien scolaire, choix d'un prof | Rassurant, factuel, orienté action |
| **Étudiants supérieurs** (18-25) | Concours, méthodo, langues | Mature, références bienvenues |
| **Adultes en reconversion** | Compétences, langues | Respecter l'expertise existante, zéro condescendance |
| **Hobbyistes** (musique, sport, arts) | Technique, matériel | Pratique, curiosité experte, humour léger ok |
| **Bien-être** | Yoga, méditation | Ton calme, moins marketing, posture de guide |

## 3. Système éducatif français

### Structure

| Niveau | Âges | Classes |
|---|---|---|
| École primaire | 6-11 | CP, CE1, CE2, CM1, CM2 |
| Collège | 11-15 | 6ème, 5ème, 4ème, 3ème |
| Lycée | 15-18 | Seconde, Première, Terminale |
| Supérieur | 18+ | Licence, Master, Doctorat, BTS, BUT, Prépa, Grandes Écoles |

### Examens clés

| Examen | Quand | Notes |
|---|---|---|
| Brevet des collèges (DNB) | fin de 3ème | premier grand examen |
| Épreuves anticipées du Bac (EAF) | fin de Première | français écrit + oral |
| Baccalauréat | fin de Terminale | 3 voies : générale, technologique, professionnelle |
| Grand oral | fin de Terminale | 20 min sur les deux spécialités (depuis 2021) |
| Concours (CPGE, Grandes Écoles) | post-bac | sélectifs |

### Spécialités du Bac général
3 spécialités en Première, 2 conservées en Terminale. Les **13 spécialités**
(stables depuis la réforme) :

- Mathématiques
- Physique-chimie
- Sciences de la vie et de la Terre (SVT)
- Numérique et sciences informatiques (NSI)
- Sciences de l'ingénieur (SI)
- Sciences économiques et sociales (SES)
- Histoire-géographie, géopolitique et sciences politiques (HGGSP)
- Humanités, littérature et philosophie (HLP)
- Langues, littératures et cultures étrangères et régionales (LLCER)
- Littérature, langues et cultures de l'Antiquité (LLCA)
- Arts (arts plastiques, musique, théâtre, cinéma-audiovisuel, danse, histoire
  des arts, arts du cirque)
- Éducation physique, pratiques et culture sportives (EPPCS)
- Biologie-écologie (lycées agricoles uniquement)

Combos courantes : Maths + Physique-Chimie, Maths + SES, SVT + Physique-Chimie,
HGGSP + SES, Langues + LLCER. Options de Terminale à connaître : **maths
complémentaires** (pour qui abandonne la spé maths) et **maths expertes** (en plus
de la spé maths).

### Voie technologique
Séries : **STMG** (management-gestion), **STI2D** (industrie et développement
durable), **ST2S** (santé-social), **STL** (laboratoire), **STD2A** (design et
arts appliqués), **STHR** (hôtellerie-restauration), **STAV** (agronomie,
lycées agricoles), **S2TMD** (théâtre, musique, danse). Ne pas les confondre avec
les anciennes séries générales S/L/ES (disparues).

### ⚠️ Contenu des programmes : toujours vérifier, jamais de mémoire
Le **contenu** d'un programme (notions d'une spécialité, œuvres au programme de
français ou de LLCER, programmes limitatifs annuels, thèmes d'HGGSP…) change
régulièrement par ajustements ministériels. Toute affirmation sur un programme se
vérifie sur **eduscol.education.fr** / **education.gouv.fr** (version en vigueur)
au moment de la rédaction — jamais reprise de l'article d'origine, jamais écrite
de mémoire. Ce fichier donne la carte (structure, noms), pas le contenu.

### Abréviations courantes
EAF, LV1/LV2, LCA, HGGSP, SES, SVT, EPS, NSI.

### Parcours supérieurs
Licence (3 ans) → Master (2) → Doctorat (3+) ; BTS (2 ans, pro) ; BUT (3 ans,
remplace le DUT) ; CPGE (2 ans) → Grandes Écoles.

### ⚠️ Pièges de fraîcheur (à détecter dans les vieux articles)
- **« Bac S/L/ES » n'existe plus** (réforme 2021) → « Bac général + spécialités ».
- **Grand oral** : introduit en 2021 ; contrôle continu repondéré depuis 2020.
- **Dates d'examens** : jamais reporter les dates de l'article d'origine — vérifier
  l'année en cours via education.gouv.fr.

## 4. Vocabulaire opérationnel

| Concept | Forme préférée | Notes |
|---|---|---|
| Cours | cours, cours particulier | « leçon » rare dans le contexte tutorat |
| Prof particulier | professeur particulier, prof particulier | « tuteur » moins grand public |
| Soutien | cours particuliers, soutien scolaire | « tutoring » = anglicisme, à éviter |
| Aide aux devoirs | aide aux devoirs | |
| Note | note (sur 20) | « la moyenne » = 10/20 |
| Réussir un examen | admis (Brevet), reçu (Bac) | |
| Échouer | ajourné, recalé (familier) | éviter « échouer à », lourd |
| Rentrée | la rentrée | |
| Révisions | révisions, préparation au Bac/Brevet | |
| Crédit d'impôt | crédit d'impôt, avance immédiate | 50 % sur les cours particuliers |
| CESU | Chèque Emploi Service Universel | |
| Spécialité | la spé maths, etc. | |
| Programme | programme scolaire | |
| Coefficient | coefficient | |
| Matière | matière | pas « sujet » |
| Sujet | sujet | « sujet du bac » = l'énoncé |
| En ligne | en ligne, à distance, par visio | éviter « online » |
| À domicile | à domicile | phrasé Superprof standard |

### À ne pas dire
- ❌ « cours en ligne » pour des cours en direct → « cours par visio » / « à distance ».
- ❌ « Bac S/L/ES » (pré-2021).
- ❌ « professeur » seul au sens commercial de prof particulier → préciser « particulier ».

### Mentions du Bac
mention assez bien (12+), bien (14+), très bien (16+), très bien avec félicitations
(selon jury).

## 5. Crédit d'impôt — phrasés validés

- **Matières scolaires** (soutien, aide aux devoirs, langue vivante scolaire) :
  - « Bénéficiez de 50 % de crédit d'impôt sur les cours particuliers »
  - « Un cours à 30 € vous revient à 15 € après crédit d'impôt »
  - « Éligible à l'avance immédiate du crédit d'impôt »
- **CESU** : « Payez en CESU et bénéficiez du crédit d'impôt »
- **Matières loisir** (yoga, piano, sport, fitness, bien-être) : le crédit d'impôt
  **ne s'applique pas** à la plupart d'entre elles → **ne jamais le revendiquer**.
  Signal de confiance alternatif : « Zéro commission », « Premier cours offert »,
  « Sans engagement ».

> **Refresh** : beaucoup de vieux articles revendiquent à tort les 50 % sur des
> matières non éligibles — vérifier et corriger. Toute claim chiffrée sur le crédit
> d'impôt se recoupe avec impots.gouv.fr.

## 6. Signaux de confiance

Quand le sujet s'y prête, tisser (sans jamais empiler les quatre) :
avis vérifiés · premier cours offert · diplômes vérifiés · CESU + crédit d'impôt
(si éligible, cf. §5). Éviter les grappes de signaux à chaque CTA.

## 7. Mots-clés — intentions à écarter

Motifs qui signalent une **mauvaise intention** pour Superprof (à dé-prioriser dans
le ciblage) :

| Motif | Raison | Quoi faire |
|---|---|---|
| « prof de [matière] » seul | souvent intention candidat-prof | ne garder que combiné à une intention consommateur (« trouver un prof de… ») |
| « devenir professeur », « comment devenir prof » | intention emploi | écarter |
| « pas cher » | chasseur de prix, faible conversion | pas en title/heading ; prix mentionnable en contexte |
| « gratuit » seul | chasseur de gratuit | ne rien promettre de gratuit hors offre réelle |
| « emploi », « job », « salaire » | intention emploi | écarter |

### Termes à intention transactionnelle (signal positif)
prof / professeur(e) · cours particulier(s) · soutien scolaire · aide aux devoirs ·
près de chez moi/vous · à domicile · en ligne / à distance / par visio ·
préparer/réviser le bac.

### Villes « local boost »
paris, lyon, marseille, toulouse, nice, nantes, strasbourg, montpellier, bordeaux,
lille, rennes, reims, le havre, saint-étienne, toulon, grenoble, dijon, angers,
nîmes, villeurbanne, saint-denis, aix-en-provence, brest, le mans, amiens, tours,
limoges, clermont-ferrand, besançon, metz. (Rare en contenu blog, portée nationale —
utile quand l'article a un ancrage régional.)

## 8. Sensibilités & cadre légal

- **Religion** : cadre de laïcité — factuel, jamais de prise de position.
- **Politique** : neutralité stricte.
- **Corps, poids, alimentation, santé mentale** : YMYL — sources médicales /
  institutionnelles uniquement.
- **Ne jamais affirmer** : que Superprof « garantit » la réussite ; des gains de
  notes chiffrés sans donnée vérifiée ; des avantages fiscaux au-delà du légal (§5).

## 9. Sources françaises préférées (bloc Sources)

Complète l'annuaire par matière `sites/superprof.fr-ressources/sources/authority-map.md`
et la blacklist `.claude/skills/source-research/references/blacklisted-domains.md`.

**Officiel** : education.gouv.fr · impots.gouv.fr · insee.fr · legifrance.gouv.fr ·
data.gouv.fr · vie-publique.fr.
**Académique** : HAL (hal.science) · Cairn.info · Persée · OpenEdition.
**Presse nationale de qualité** : Le Monde, Le Figaro, Libération, La Croix,
Les Échos, Le Point, L'Express, France Info / Radio France.
**Spécialistes** : Cnesco (évaluation scolaire), France Stratégie, Cevipof,
rapports OCDE sur la France.

**À éviter** : Wikipédia (remonter à ses sources), forums (Doctissimo, Reddit…),
blogs perso sans auteur identifié, plateformes concurrentes, contenus sponsorisés.

## 10. Auteurs francophones citables (par domaine)

À utiliser **au service d'un argument précis**, jamais en décoration.

- **Institutions, inégalités, société** : Hugo, Zola, Camus, Bourdieu, Piketty,
  Annie Ernaux (Nobel 2022), Edgar Morin.
- **Éducation** : Edgar Morin, Durkheim, Bourdieu (reproduction culturelle),
  Philippe Meirieu (pédagogie contemporaine).
- **Philosophie** : Bergson, Merleau-Ponty, Simone de Beauvoir, Simone Weil,
  Camus, Hannah Arendt.
- **Sciences** : Marie et Pierre Curie, Poincaré, Étienne Klein (vulgarisation),
  Cédric Villani (maths).
- **Arts & lettres** : Proust, Duras, Ernaux, Michon, Modiano (Nobel 2014).
- **Sport & société** : Lilian Thuram, Marie-José Pérec.

## 11. Institutions pour les exemples

- **Universités** : Sorbonne Université, Paris-Saclay, Sciences Po, ENS,
  Polytechnique, Dauphine, Aix-Marseille, Strasbourg.
- **Lycées prestigieux** : Henri-IV, Louis-le-Grand (Paris), Lycée du Parc (Lyon),
  Pierre-de-Fermat (Toulouse), Sainte-Geneviève « Ginette » (Versailles).
- **Grandes Écoles** : HEC, ESSEC, ESCP ; Polytechnique, CentraleSupélec,
  Mines ParisTech ; Sciences Po ; ENS Ulm / Lyon.
- **Culture** : BnF, Louvre, Centre Pompidou, Orsay, Comédie-Française,
  Académie française.

## 12. Références culturelles — valeurs sûres

- **Littérature** : Les Misérables, Madame Bovary, L'Étranger, Le Petit Prince.
- **Cinéma** : Nouvelle Vague, Intouchables, Les Choristes, Cannes.
- **Musique** : chanson française (Brel, Brassens, Piaf) ; contemporain (Stromae,
  Aya Nakamura, Christine and the Queens).
- **Séries** : Lupin, Dix pour cent, Le Bureau des Légendes.
- **Sport** : Coupe du Monde (1998, 2018), Tour de France, Roland-Garros.

### À éviter comme références par défaut
Villes/figures étrangères sans lien avec le sujet · comparaisons scolaires
US-centrées (SAT, GPA) · presse UK/US quand un équivalent FR existe · montants en
dollars/livres (convertir en euros) · médicaments/compléments nommés sans citation
médicale (YMYL).

## 13. Calendrier scolaire & fériés

**Calendrier** (varie par zones A/B/C — vérifier les dates exactes avant de citer) :
rentrée début septembre · Toussaint fin oct.-début nov. · Noël fin décembre ·
Hiver février (zoné) · Printemps avril (zoné) · Été début juillet → début septembre.

**Examens** (vérifier chaque année via education.gouv.fr) : Brevet mi-fin juin ·
Bac spécialités écrites mars · philo + EAF juin · Grand oral mi-juin/début juillet ·
oraux LV mai-juin.

**Fériés** : 14 juillet, 8 mai, 11 novembre, 1er novembre, 25 décembre, Pâques
(mobile), Fête de la musique 21 juin. (Pour la programmation éditoriale :
[[feedback-french-holidays-calendar]].)

---

## Renvois

- Typographie française → `.claude/skills/format-wordpress/references/typographie-fr.md`
- Blacklist de domaines → `.claude/skills/source-research/references/blacklisted-domains.md`
- Annuaire d'autorité par matière → `sites/superprof.fr-ressources/sources/authority-map.md`
- Ton, structure, blocs → `prompts/site.md` + [[sp-ressources-gutenberg]]
