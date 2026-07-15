# Référence HTML Gutenberg — Séraphine

**Objectif** : ce fichier contient le HTML propre, formaté Gutenberg, que le LLM doit suivre comme **référence canonique** pour structurer ses outputs dans `_shared/outputs/{site}/html/`.

**Usage** : chargé dynamiquement par le pipeline en complément de `sites/superprof-ressources.md`. Le LLM doit reproduire à l'identique :
- la structure des blocs Gutenberg (commentaires `<!-- wp:* -->`)
- les classes CSS WordPress (`wp-block-*`, `advgb-*`, `superprof-*`)
- les attributs JSON dans les commentaires d'ouverture de bloc
- l'ordre et l'imbrication des balises

**Règle** : si un détail de format diverge entre cette référence et `superprof-ressources.md`, **cette référence prévaut** (elle reflète la réalité WordPress backoffice).

---

## Article de référence

> Coller ci-dessous le HTML complet d'un article validé en production, formaté Gutenberg-ready.
> Idéalement choisir un article qui contient tous les blocs canoniques (Info Box jaune, Info Box bleue, Citation, Count-Up, Sources) + au moins un bloc optionnel utilisé (Presentation Card / Timeline / Poll).

```html
<!-- wp:heading {"level":1} -->
<h1 class="wp-block-heading">Relief, régions, fleuves et caractéristiques géographiques du territoire français</h1>
<!-- /wp:heading -->

<!-- wp:advgb/count-up {"id":"count-up-e8b277a1-a972-4c25-957b-f567aefbd510","headerText":"La France s'étend sur","countUpNumber":"551695 km²\u003cbr\u003e ","countUpNumberColor":"#157dfe","descText":"de territoire métropolitain","changed":true,"metadata":{"categories":[],"patternName":"core/block/143980","name":"Count up blue"}} -->
<div class="wp-block-advgb-count-up advgb-count-up count-up-e8b277a1-a972-4c25-957b-f567aefbd510" style="display:flex"><div class="advgb-count-up-columns-one"><h4 class="advgb-count-up-header">La France s'étend sur</h4><div class="advgb-counter" style="color:#157dfe;font-size:55px"><span class="advgb-counter-number">551695 km²<br> </span></div><p class="advgb-count-up-desc">de territoire métropolitain</p></div></div>
<!-- /wp:advgb/count-up -->

<!-- wp:paragraph -->
<p><span style="box-sizing: border-box; margin: 0px; padding: 0px;">Ses six massifs montagneux, cinq grands fleuves, et sa façade maritime font de la&nbsp;<strong>géographie de la France</strong>&nbsp;une merveille à la fois variée et fascinante.</span> C'est d'ailleurs pour ça qu'elle revient si souvent dans les cours de géo, du CM2 au lycée.</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p>Dans ce guide, tu trouveras tout ce qu'il faut savoir sur la France : sa superficie, son relief, ses régions administratives, ses principaux fleuves et ses territoires d'outre-mer. Que tu aies un devoir à rendre ou un contrôle à préparer, cette fiche est faite pour toi. C'est parti !</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">La France en chiffres : superficie et position géographique 📐</h2>
<!-- /wp:heading -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">🗺️ Où se trouve la France ?</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>La France métropolitaine est située en <strong>Europe occidentale</strong>, entre l'Atlantique à l'ouest, la mer Méditerranée au sud-est et le Rhin à l'est. </p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p>La France partage ses frontières terrestres avec six pays : </p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list"><!-- wp:list-item -->
<li>🇧🇪 la Belgique au nord-est</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>🇱🇺 le Luxembourg au nord-est</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>🇩🇪 l'Allemagne au nord-est</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>🇨🇭la Suisse à l'est</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>🇮🇹 l'Italie à l'est </li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>🇪🇸 l'Espagne au sud </li>
<!-- /wp:list-item --></ul>
<!-- /wp:list -->

<!-- wp:paragraph -->
<p>Cette position centrale en fait une véritable plaque tournante du continent européen. Sa forme hexagonale lui a d'ailleurs valu le surnom d'<strong>Hexagone</strong> — un mot que tu croiseras souvent pour désigner la France métropolitaine, par opposition aux territoires ultramarins. Du nord au sud, la France s'étend sur environ 1 000 km ; d'ouest en est, la distance est similaire.</p>
<!-- /wp:paragraph -->

<!-- wp:advgb/infobox {"blockIDX":"advgb-infobox-21cc0ee7-988a-48dd-b3b2-6a44e30604b9","containerBorderWidth":2,"containerBackground":"#e8f2ff","containerBorderBackground":"#157dfe","iconBackground":"#e8f2ff","iconColor":"#157dfe","title":"\u003cstrong\u003eSavais-tu d'où vient le nom d'Hexagone pour designer la France métropolitaine?\u003c/strong\u003e","titleHtmlTag":"div","text":"\u003cstrong\u003eL'Hexagone\u003c/strong\u003e — un mot que tu croiseras souvent pour désigner la France métropolitaine, par opposition aux territoires ultramarins vient tous simplement de sa forme. \u003cbr\u003e\u003cbr\u003e Du nord au sud, la France s'étend sur environ \u003cstrong\u003e1 000 km\u003c/strong\u003e ; d'ouest en est, la distance est similaire.","changed":true,"metadata":{"categories":[],"patternName":"core/block/143977","name":"Info Box Blue"}} -->
<div class="wp-block-advgb-infobox advgb-infobox-wrapper has-text-align-center advgb-infobox-21cc0ee7-988a-48dd-b3b2-6a44e30604b9"><div class="advgb-infobox-wrap"><div class="advgb-infobox-icon-container"><div class="advgb-infobox-icon-inner-container"><i class="material-icons-outlined">beenhere</i></div></div><div class="advgb-infobox-textcontent"><div class="advgb-infobox-title"><strong>Savais-tu d'où vient le nom d'Hexagone pour designer la France métropolitaine?</strong></div><p class="advgb-infobox-text"><strong>L'Hexagone</strong> — un mot que tu croiseras souvent pour désigner la France métropolitaine, par opposition aux territoires ultramarins vient tous simplement de sa forme. <br><br> Du nord au sud, la France s'étend sur environ <strong>1 000 km</strong> ; d'ouest en est, la distance est similaire.</p></div></div></div>
<!-- /wp:advgb/infobox -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">📊 Superficie de la France</h3>
<!-- /wp:heading -->

<!-- wp:shortcode -->
[table id=2270 /]
<!-- /wp:shortcode -->

<!-- wp:paragraph -->
<p>Avec 551 695 km², la France est le <strong>plus grand pays de l'Union Européenne</strong>. Elle est environ deux fois plus grande que l'Allemagne et cinq fois plus grande que la Suisse. Si l'on ajoute les territoires d'outre-mer, la superficie totale dépasse 643 000 km².</p>
<!-- /wp:paragraph -->

<!-- wp:advgb/infobox {"blockIDX":"advgb-infobox-cabc69c0-434c-441b-9855-6dd4a95337c6","containerBorderWidth":2,"containerBackground":"#fffbf0","containerBorderBackground":"#ffcf3b","iconBackground":"#fffbf0","iconColor":"#ffcf3b","title":"Le bon réflexe pour retenir la superficie","titleHtmlTag":"div","text":"\u003cstrong\u003e551 695 km² pour la France métropolitaine \u003cbr\u003e\u003c/strong\u003eun chiffre facile à retenir si tu penses à\u003cstrong\u003e 552 000 km² (arrondis)\u003c/strong\u003e.\u003cbr\u003e\u003cbr\u003eRappelle-toi aussi que la Guyane française, seule, fait presque autant que l'Autriche et la Suisse réunies !","changed":true} -->
<div class="wp-block-advgb-infobox advgb-infobox-wrapper has-text-align-center advgb-infobox-cabc69c0-434c-441b-9855-6dd4a95337c6"><div class="advgb-infobox-wrap"><div class="advgb-infobox-icon-container"><div class="advgb-infobox-icon-inner-container"><i class="material-icons-outlined">beenhere</i></div></div><div class="advgb-infobox-textcontent"><div class="advgb-infobox-title">Le bon réflexe pour retenir la superficie</div><p class="advgb-infobox-text"><strong>551 695 km² pour la France métropolitaine <br></strong>un chiffre facile à retenir si tu penses à<strong> 552 000 km² (arrondis)</strong>.<br><br>Rappelle-toi aussi que la Guyane française, seule, fait presque autant que l'Autriche et la Suisse réunies !</p></div></div></div>
<!-- /wp:advgb/infobox -->

<!-- wp:heading -->
<h2 class="wp-block-heading">Le relief de la France : montagnes, plaines et collines 🏔️</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Le relief français est <strong>très varié</strong> : des hauts sommets alpins aux vastes plaines du Bassin parisien, en passant par les plateaux du Massif central. C'est l'un des aspects les plus riches à étudier dans la géographie de la France.</p>
<!-- /wp:paragraph -->

<!-- wp:advgb/count-up {"id":"count-up-23cb6fbf-e164-4237-9f7d-0fa7f30ca0f1","headerText":"Altitude du mont Blanc","countUpNumber":"4809","countUpNumberColor":"#157dfe","descText":"mètres — point culminant de France et d'Europe occidentale (Source : IGN, 2023)","changed":true} -->
<div class="wp-block-advgb-count-up advgb-count-up count-up-23cb6fbf-e164-4237-9f7d-0fa7f30ca0f1" style="display:flex"><div class="advgb-count-up-columns-one"><h4 class="advgb-count-up-header">Altitude du mont Blanc</h4><div class="advgb-counter" style="color:#157dfe;font-size:55px"><span class="advgb-counter-number">4809</span></div><p class="advgb-count-up-desc">mètres — point culminant de France et d'Europe occidentale (Source : IGN, 2023)</p></div></div>
<!-- /wp:advgb/count-up -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">⛰️ Les principaux massifs montagneux</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>La France possède six grands ensembles montagneux, répartis surtout sur ses marges est et sud :</p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list"><!-- wp:list-item -->
<li>Les <strong>Alpes</strong> (à l'est) : le massif le plus imposant, avec le <strong>mont Blanc à 4 809 m</strong> — point culminant de France et d'Europe occidentale,</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>Les <strong>Pyrénées</strong> (au sud) : frontière naturelle avec l'Espagne, culminant au pic d'Aneto côté espagnol et au <strong>pic Vignemale (3 298 m) côté français</strong>,</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>Le <strong>Massif central</strong> (au centre) : vieux massif volcanique érodé, avec son point culminant au <strong>Puy de Sancy (1 885 m)</strong>,</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>Les <strong>Vosges</strong> (à l'est) : massif arrondi et boisé, culminant au <strong>Grand Ballon (1 424 m)</strong>,</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>Le <strong>Jura</strong> (à l'est) : plateaux calcaires aux paysages karstiques, avec le <strong>Crêt de la Neige (1 720 m)</strong>,</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>Les <strong>Ardennes</strong> (au nord-est) : prolongement du Massif rhénan, relief modéré et très boisé.</li>
<!-- /wp:list-item --></ul>
<!-- /wp:list -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">🌾 Les grandes plaines et bassins sédimentaires</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Entre ces massifs s'étendent de vastes plaines sédimentaires, essentielles à l'agriculture française 🚜. Le Bassin parisien est le plus important : il s'étend sur plus d'un tiers du territoire métropolitain et concentre une grande partie de la population. Au sud-ouest, le Bassin aquitain offre des terres fertiles et un climat propice aux cultures. Ces deux bassins sont séparés par le Massif central.</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">🌊 Le littoral français</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>La France possède un littoral de près de <strong>5 500 km</strong> (hors îles et territoires ultramarins), ce qui lui confère une façade maritime exceptionnelle. Au nord et à l'ouest, les côtes atlantiques et de la Manche sont souvent découpées et exposées aux vents. Au sud, la côte méditerranéenne est plus linéaire, marquée par des plages de sable fin et des calanques. La Corse, quant à elle, offre 1 000 km de côtes supplémentaires.</p>
<!-- /wp:paragraph -->

<!-- wp:advgb/infobox {"blockIDX":"advgb-infobox-add4c7a0-e979-43a9-85cc-0ede2dfdc13d","containerBorderWidth":2,"containerBackground":"#e8f2ff","containerBorderBackground":"#157dfe","iconBackground":"#e8f2ff","iconColor":"#157dfe","title":"\u003cstrong\u003eAstuce mémo : les 6 massifs\u003c/strong\u003e","titleHtmlTag":"div","text":"Pour retenir les 6 massifs montagneux français, pense à la règle \u003cstrong\u003eAMVJJA\u003c/strong\u003e : \u003cbr\u003eAlpes, Massif central, Vosges, Jura, Jura, Ardennes. \u003cbr\u003eUne carte muette à compléter régulièrement est le meilleur moyen de les mémoriser durablement.","changed":true} -->
<div class="wp-block-advgb-infobox advgb-infobox-wrapper has-text-align-center advgb-infobox-add4c7a0-e979-43a9-85cc-0ede2dfdc13d"><div class="advgb-infobox-wrap"><div class="advgb-infobox-icon-container"><div class="advgb-infobox-icon-inner-container"><i class="material-icons-outlined">beenhere</i></div></div><div class="advgb-infobox-textcontent"><div class="advgb-infobox-title"><strong>Astuce mémo : les 6 massifs</strong></div><p class="advgb-infobox-text">Pour retenir les 6 massifs montagneux français, pense à la règle <strong>AMVJJA</strong> : <br>Alpes, Massif central, Vosges, Jura, Jura, Ardennes. <br>Une carte muette à compléter régulièrement est le meilleur moyen de les mémoriser durablement.</p></div></div></div>
<!-- /wp:advgb/infobox -->

<!-- wp:heading -->
<h2 class="wp-block-heading">Les fleuves et le réseau hydrographique français 🌊</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>La France est traversée <strong>par cinq grands fleuves</strong> qui structurent son territoire et ont façonné son histoire. Les connaître, c'est aussi comprendre comment les villes se sont développées et comment le pays s'est organisé au fil des siècles.</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">🏞️ Les cinq grands fleuves</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p><strong>La</strong> <strong>Loire</strong> est le plus long fleuve entièrement français. Son val est classé au patrimoine mondial de l'UNESCO pour ses châteaux et ses paysages. <strong>La&nbsp;Seine</strong>, même si elle est plus courte, est stratégique : elle traverse Paris et se jette dans la Manche, faisant de la capitale une ville à la fois fluviale et maritime.</p>
<!-- /wp:paragraph -->

<!-- wp:shortcode -->
[table id=2271 /]
<!-- /wp:shortcode -->

<!-- wp:superprof/quote-block {"quote":"La France est un pays fait pour être traversé. Ses fleuves s'écoulent vers quatre mers différentes : l'Atlantique, la Manche, la Méditerranée et la mer du Nord. C'est une caractéristique unique en Europe.","citation":"Roger Brunet, géographe, La France, un territoire entre histoire et géographie (2001)"} -->
<blockquote class="wp-block-superprof-quote-block"><p>La France est un pays fait pour être traversé. Ses fleuves s'écoulent vers quatre mers différentes : l'Atlantique, la Manche, la Méditerranée et la mer du Nord. C'est une caractéristique unique en Europe.</p><cite>Roger Brunet, géographe, La France, un territoire entre histoire et géographie (2001)</cite></blockquote>
<!-- /wp:superprof/quote-block -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">🌧️ Le réseau de rivières</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Au-delà des cinq grands fleuves, la France possède un réseau hydrographique très dense, avec des milliers de rivières et d'affluents. </p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list"><!-- wp:list-item {"className":"has-16-font-size"} -->
<li class="has-16-font-size"><strong>La Dordogne</strong> au sud-ouest</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li><strong>Le</strong> <strong>Lot</strong> au sud-ouest</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li><strong>La</strong> <strong>Saône</strong> à l'est (principal affluent du Rhône)</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li><strong>La</strong> <strong>Marne</strong> (affluent de la Seine)</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li> <strong>L'Oise</strong> au nord (affluent de la Seine)</li>
<!-- /wp:list-item --></ul>
<!-- /wp:list -->

<!-- wp:paragraph -->
<p>Chacun de ces cours d'eau a structuré des régions entières. </p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p>Ce réseau est essentiel pour: </p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list"><!-- wp:list-item -->
<li>💧 L'irrigation agricole</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>⚡️La production d'hydroélectricité </li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>⛴️ Le transport fluvial</li>
<!-- /wp:list-item --></ul>
<!-- /wp:list -->

<!-- wp:heading -->
<h2 class="wp-block-heading">Régions administratives, climats et outre-mer 🗺️</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>La géographie de la France, c'est aussi son organisation administrative et la diversité de ses territoires. Depuis la réforme de 2016, la France métropolitaine est divisée en <strong>13 régions</strong>, auxquelles s'ajoutent 5 régions d'outre-mer.</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">🏛️ Les 13 régions métropolitaines</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>La réforme territoriale de 2016 a réduit le nombre de régions métropolitaines de 22 à 13. Ces régions sont : Auvergne-Rhône-Alpes, Bourgogne-Franche-Comté, Bretagne, Centre-Val de Loire, Corse, Grand Est, Hauts-de-France, Île-de-France, Normandie, Nouvelle-Aquitaine, Occitanie, Pays de la Loire et Provence-Alpes-Côte d'Azur. Chaque région dispose d'un conseil régional élu et d'un chef-lieu. La plus grande en superficie est la <strong>Nouvelle-Aquitaine</strong> (84 036 km²), et la plus petite, l'<strong>Île-de-France</strong> (12 012 km²) — qui est pourtant la plus peuplée du pays.</p>
<!-- /wp:paragraph -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">🌡️ La diversité climatique</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>La France connaît <strong>quatre grands types de climat</strong>, qui expliquent la diversité de ses paysages et de son agriculture :</p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list"><!-- wp:list-item -->
<li>🌊 <strong>Climat océanique</strong> (façade atlantique et nord-ouest) : hivers doux et pluvieux, étés frais,</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>🌳 <strong>Climat continental</strong> (centre et est) : hivers froids et étés chauds, précipitations réparties sur l'année,</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>⛱️ <strong>Climat méditerranéen</strong> (sud et Corse) : étés chauds et secs, hivers doux et humides,</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>⛰️<strong>Climat de montagne</strong> (Alpes, Pyrénées, Massif central) : températures fraîches, enneigement important en altitude.</li>
<!-- /wp:list-item --></ul>
<!-- /wp:list -->

<!-- wp:heading {"level":3} -->
<h3 class="wp-block-heading">🌴 Les territoires d'outre-mer (DOM-TOM)</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>La France est l'un des rares pays à disposer de territoires dans tous les océans du monde. Les cinq départements et régions d'outre-mer (DROM) sont : la Guadeloupe et la Martinique (Antilles), la Guyane (Amérique du Sud), La Réunion (océan Indien) et Mayotte (canal du Mozambique). À ces DROM s'ajoutent des collectivités d'outre-mer comme Saint-Martin, Saint-Barthélemy, la Polynésie française et la Nouvelle-Calédonie. Cette présence mondiale fait de la France la&nbsp;deuxième puissance économique mondiale, avec plus de 11 millions de km² de zone économique exclusive (ZEE), après les États-Unis.</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p>La <strong>géographie de la France</strong> est l'une des plus riches d'Europe : une superficie de 551 695 km², six massifs montagneux, cinq grands fleuves, quatre types de climat et des territoires répartis sur tous les océans du monde. Maîtriser ces éléments — relief, hydrographie, régions, climat — te donnera une base solide pour tous tes cours de géographie, du brevet au bac. Si tu veux aller encore plus loin, un professeur particulier de géographie peut t'aider à consolider tes connaissances et à préparer tes examens avec méthode.</p>
<!-- /wp:paragraph -->

<!-- wp:group -->
<div class="wp-block-group"><!-- wp:group {"className":"wp-block-wp-sp-gutenberg-blocks-block-sources"} -->
<div class="wp-block-group wp-block-wp-sp-gutenberg-blocks-block-sources"><!-- wp:heading -->
<h2 class="wp-block-heading">Sources 📚</h2>
<!-- /wp:heading -->

<!-- wp:list {"ordered":true,"className":"references"} -->
<ol class="wp-block-list references"><!-- wp:list-item -->
<li>Institut Géographique National (IGN). <em>Atlas de France — Territoire et société.</em> IGN, Paris, 2023, <a href="https://www.ign.fr" target="_blank" rel="noopener">https://www.ign.fr</a>.</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>INSEE. "Superficie des régions françaises." <em>Institut national de la statistique et des études économiques</em>, 2023, <a href="https://www.insee.fr/fr/statistiques/2011101" target="_blank" rel="noopener">https://www.insee.fr/fr/statistiques/2011101</a>.</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>Ministère de la Transition écologique. <em>Chiffres clés du climat France, Europe et Monde.</em> SDES, Paris, 2024, <a href="https://www.statistiques.developpement-durable.gouv.fr" target="_blank" rel="noopener">https://www.statistiques.developpement-durable.gouv.fr</a>.</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>UNESCO. "Val de Loire — paysage culturel." <em>Liste du patrimoine mondial de l'UNESCO</em>, 2000, <a href="https://whc.unesco.org/fr/list/933" target="_blank" rel="noopener">https://whc.unesco.org/fr/list/933</a>.</li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li>Brunet, Roger, Robert Ferras et Hervé Théry. <em>Les Mots de la géographie : dictionnaire critique.</em> La Documentation française / Reclus, Paris, 1993. (Référence académique.)</li>
<!-- /wp:list-item --></ol>
<!-- /wp:list --></div>
<!-- /wp:group --></div>
<!-- /wp:group -->

<!-- wp:paragraph -->
<p></p>
<!-- /wp:paragraph -->
```

---

## Variantes par type de contenu (optionnel)

Si plusieurs formats canoniques émergent (guide long, listicle, comparatif), ajouter une section par format ci-dessous avec son propre exemple HTML.

### Guide long

```html
<!-- HTML guide long -->
```

### Listicle

```html
<!-- HTML listicle -->
```

### Comparatif

```html
<!-- HTML comparatif -->
```
