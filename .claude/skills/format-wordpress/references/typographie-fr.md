# French typography & language mechanics

**Language** mechanics for all French-language content (all FR sites):
non-breaking spaces, quotation marks, apostrophe, numbers, capitalisation, AI
connector phrases to ban, anglicisms. Imported from the `blog-refresh.skill`
package (July 2026) and adapted to the repo's rules. Complements the `SKILL.md`
of `format-wordpress` (HTML/WP invariants); country knowledge (school system,
trade vocabulary) lives on the site side
(e.g. `connaissance-fr.md` in [[sp-ressources-gutenberg]]).

## 1. Non-breaking spaces (NBSP)

French requires a **non-breaking space before** these signs (unlike
English):

| Sign | Form | Example |
|---|---|---|
| `:` `;` `?` `!` | `texte⎵:` | `Le résultat⎵: 15/20` |
| `%` | `nombre⎵%` | `15⎵%` |
| `€` | `nombre⎵€` | `30⎵€` |
| `«` `»` | `«⎵texte⎵»` | NBSP inside the quotation marks |

Where `⎵` = non-breaking space (U+00A0). In the output HTML, use the literal
U+00A0 character or `&nbsp;`; do not rely on WordPress auto-correcting on
paste. Old articles often have missing NBSPs: detect and fix them during the
refresh.

## 2. Quotation marks

- **« … » (French guillemets)** for direct quotes and titles of works
  in the body, with NBSPs inside.
- **" … " (English quotation marks)**: avoid in French text; a telltale sign
  of translated or generated text.
- **' … '**: only inside a nested English quotation.

## 3. Apostrophe

**Typographic** apostrophe `'` (U+2019), never the straight one `'` (U+0027):
`aujourd'hui`, `l'oral`.

## 4. Dashes

- **Em dash `—`: forbidden everywhere** (all sites, body and JSON):
  [[feedback-no-em-dash]]. For parentheticals: commas, parentheses, or an
  en dash `–` if a visual separator is indispensable.
- **En dash `–`**: number ranges (`pages 12–15`, `2010–2024`),
  never as a rhythm crutch in prose.

## 5. Inclusive writing: the middle dot

The **middle dot** is allowed when it stays natural: `un·e prof·e
expérimenté·e`, `chaque étudiant·e`, `devenir fort·e en espagnol`.

- **Prefer rephrasing first** to avoid gendering (epicene word, neutral
  phrasing); the middle dot is for when rephrasing weighs the sentence down
  more than it helps.
- Avoid chaining several middle-dot forms in the same sentence
  (unreadable), and in **headings** (hurts scannability).
- Character: **typographic middle dot** `·` (U+00B7), not a period.
- Consistency per article: if the original article uses it, keep going;
  otherwise, decide per article based on the audience.

## 6. Numbers

| Format | Rule | Example |
|---|---|---|
| Thousands | non-breaking space | `1⎵234⎵567` |
| Decimal | comma | `12,5` |
| Currency | `30⎵€`, never `€30` | |
| Percentage | `15⎵%` | |
| Phone | spaces in pairs | `01 23 45 67 89` |

- **Zero to nine**: spelled out (`trois élèves`); **10 and above**: digits.
- Statistics, prices, percentages, dates: always digits.
- Dates: `le 15 mars 2026` (body text) or `15/03/2026`; never ISO
  `2026-03-15` nor US format in prose.

## 7. Italics

Only for: foreign words embedded in a French sentence (`un effet
*flow*`, `*et al.*`) and titles of works (`*Les Misérables*`). **Never for
emphasis**; use bold sparingly instead.

## 8. Capitalisation

French content:

- **Lowercase**: languages (`l'espagnol`), school subjects (`les mathématiques`),
  grade levels (`la terminale`), days and months (`lundi 15 mars`, `en septembre`).
- **Uppercase**: exam names (`le Baccalauréat`, `le Brevet`, `le Bac`),
  institutions (`l'Éducation nationale`).
- **Titles and headings: sentence case**, never Title Case.
  - ✅ `Oral d'espagnol au bac : exemples de thèmes et conseils`
  - 🚫 `Oral d'Espagnol au Bac : Exemples de Thèmes et Conseils`

## 9. AI connector phrases to ban (FR)

Tics of generated text; detect and replace with native phrasing:

| AI tic | Alternative |
|---|---|
| Il est important de noter que | (delete) / À noter |
| En outre | Et / D'ailleurs |
| Par ailleurs | D'ailleurs / Or |
| De plus | Et / En plus |
| Il convient de mentionner | (delete) / On peut citer |
| Dans le cadre de | Pour / Lors de |
| Au niveau de | Sur / Pour |
| Force est de constater | (delete) / Manifestement |
| Plonger dans (l'univers de) | Découvrir / Explorer |
| Tisser des liens | Créer des liens |
| Naviguer (les complexités) | Avancer dans / Traverser |
| Embrasser (le défi) | Relever / S'attaquer à |
| En effet | (often deletable) / De fait |
| C'est-à-dire que | Autrement dit |
| Dans un monde où… | (opening cliché; get straight to the point) |

**Connectors that sound native**: D'ailleurs · Or · En revanche · Cela dit ·
Reste que · À vrai dire · Quand même · Bref · Au fond. (`Du coup`: colloquial,
use sparingly.)

**Filler to cut**: `tout simplement`, `très très`, `assez` / `un peu` /
`vraiment` / `bien` when they add nothing.

## 10. Common mistakes to catch during a refresh

| Anti-pattern | Fix |
|---|---|
| tu/vous mixed within one article | pick one based on the audience (and the site's skill), make it uniform |
| `Lundi`, `Septembre` mid-sentence | lowercase |
| `L'Espagnol` (the language) | `l'espagnol` |
| `15%`, `30€` | NBSP: `15⎵%`, `30⎵€` |
| `« texte »` with regular spaces | NBSPs inside |
| English `"texte"` in French text | `«⎵texte⎵»` |
| Straight apostrophe `'` | typographic `'` |
| Any `—` | forbidden; commas, parentheses or `–` ([[feedback-no-em-dash]]) |
| « challenger » (verb) | défier, remettre en question |
| « checker » | vérifier |
| « supporter » (meaning to back) | soutenir, appuyer |
| « performer » (verb) | réussir, donner le meilleur |

## 11. Tolerated anglicisms

Established in French usage, less disruptive than their translation: le coach /
coacher (« entraîneur » preferred for sport) · le brief · le marketing · le
management · le test · le job (colloquial; prefer « travail »/« poste » in
formal register). Non-naturalised borrowings are set in italics: `un *workflow*
fluide`, `le *small talk*`.
