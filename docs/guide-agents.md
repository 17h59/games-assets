# Guide des agents

[← Sommaire](README.md) · fichier : `tools/AGENT_GUIDE.md` · voir aussi [Délégation](delegation.md)

`tools/AGENT_GUIDE.md` est la consigne que chaque agent lit en entier avant de travailler. Il contient :
les commandes `sk` utiles, les fichiers à regarder ([QA](qa.md)), ce qu'est un bon résultat, une table
**symptôme → correction**, les [zones](zones.md), les modes de [regroupement](entites.md), la méthode
(≤ 6 allers-retours, réglages globaux puis cas isolés, `needs_fix` motivé), et les règles (rien à la main,
seulement les feuilles assignées).

Règle clé qui rend la délégation utile : **décrire précisément une limite de l'outil** dans la note
`needs_fix` (ce qui a été essayé, chiffres). C'est ainsi qu'ont été trouvés le plancher d'aire de
l'épluchage, le pas 31/32, et le besoin des zones, de `carve`, de `group=columns/blocks`, du fond par zone.

**À tenir à jour** : chaque nouvel outil ou paramètre doit être ajouté au guide (commandes + table de
diagnostic), sinon les agents ne l'utilisent pas.
