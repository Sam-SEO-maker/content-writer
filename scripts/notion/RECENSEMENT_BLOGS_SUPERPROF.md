# Recensement des sites Superprof (Phase 6d)

Source de vérité runtime = `_shared/config/sites.json`. Ce recensement documente
les marchés Superprof éligibles à devenir des tenants Content Writer, pour
alimenter la page Notion « config pays » (amont) puis `sites.json` (aval, via
`sync_sites_from_notion.py`).

## Sites « Ressources » Superprof (6 marchés matures)

Le blog éditorial existe dans ~90 pays (`superprof.{tld}/blog/`), mais un **site
Ressources dédié** n'existe que dans **6 marchés**. Toutes les propriétés GSC
ci-dessous sont **confirmées présentes** dans `mcp gsc-remote list_properties`
(vérifié 2026-07-15).

| Pays | URL site Ressources | GSC property | Tenant ID (convention) | url_base | Tenant CW ? |
|------|---------------------|--------------|------------------------|----------|-------------|
| FR | superprof.fr/ressources/ | `https://www.superprof.fr/ressources/` | `superprof-ressources` (dérog.) | — | ✅ existant |
| ES | superprof.es/**apuntes**/ | `https://www.superprof.es/apuntes/` | `es-es-ressources` | `/apuntes/` | ❌ candidat |
| DE | superprof.de/**lernplattform**/ | `https://www.superprof.de/lernplattform/` | `de-de-ressources` | `/lernplattform/` | ❌ candidat |
| UK | superprof.co.uk/resources/ | `https://www.superprof.co.uk/resources/` | `en-uk-ressources` | `/resources/` | ❌ candidat |
| US | superprof.com/resources/ | `https://www.superprof.com/resources/` | `en-us-ressources` | `/resources/` | ❌ candidat |
| BR | superprof.com.br/recursos/ | `https://www.superprof.com.br/recursos/` | `pt-br-ressources` | `/recursos/` | ❌ candidat |

**Pièges de chemin** : ES = `/apuntes/` (pas `/recursos/`), DE = `/lernplattform/`
(pas `/ressourcen/`). Le chemin variable vit dans `url_base` (config), **jamais
dans l'ID** (convention `lang-country-type`). Ne pas confondre le site Ressources
ES `es-es-ressources` (chemin `/apuntes/`) avec le **client autonome** `apuntes`
(marque distincte).

## Onboarding d'un candidat = zéro code

Rappel architecture (Phase 4) : onboarder un tenant = 1 dossier `tenants/{id}/`
+ 1 entrée `sites.json`, **zéro code**. La résolution GSC route automatiquement
ces 5 candidats vers le MCP `gsc-remote` (domaines `superprof.*`, cf. Phase 6c) ;
enseigna reste sur le service account.

## Chaîne de sync (Phase 6d)

```
Page Notion « config pays »   (source humaine, éditée)
   │  sync unidirectionnel : python -m scripts.notion.sync_sites_from_notion --apply
   ▼
_shared/config/sites.json     (index machine UNIQUE — pas de markets.json séparé)
   │
   ▼
moteur (runtime)              (lit sites.json, JAMAIS Notion)
```

Le sync est **additif** : il préserve tous les champs existants et les clés
top-level ; il n'écrase que ce que Notion fournit. `--dump-schema` affiche les
propriétés réelles de la base pour caler `PROPERTY_MAP` au 1er run.

## Marchés SANS site Ressources (hors périmètre)

Canada, Mexique, Italie, et tout LATAM hispanophone (AR/CL/CO/PE…) n'ont **pas**
de site Ressources. Cibles naturelles de futurs tenants sur le modèle FR : les 5
candidats ci-dessus (ES, DE, UK, US, BR).
