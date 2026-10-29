# Ensembles par légende

[← Sommaire](README.md) · code : `extract.caption_sets`, `assign_sets`, `qa.captions` · voir aussi [Entités](entites.md)

Problème d'origine : les feuilles d'effets (« Fire-Type Moves »...) rangent chaque attaque sous une
**légende** du ripper, avec ses frames ET ses particules ; sorties en éléments isolés, tout était mélangé.

## `sets=captions` (défaut depuis la migration)
1. **Lignes de légende** : éléments `text`, ou jetés (`dropped`) de hauteur ≤ `text_max_h`, regroupés par
   ligne de base (± 3 px, écart ≤ 10 px) ; une ligne = ≥ 2 morceaux ou ≥ 12 px de large.
2. Rattachement par **segment de rangée** (sprites consécutifs, coupés aux trous `row_split_gap`), par
   priorité : légende sur la même rangée à gauche ; à droite ; sinon légende au-dessus — parmi les plus
   basses (à 8 px près), celle qui **commence au-dessus du segment**, sinon la plus proche à sa gauche.
   (Règle d'origine « au-dessus et à gauche, sprite par sprite » : échouait pour deux légendes sur la même
   ligne — Floormaster / Wallmaster.) Correction manuelle : `sk setbox ID Sn x,y,w,h`.
3. Les fichiers vont dans un **sous-dossier par ensemble** (`set_NN/` ou le nom donné) ; le manifest a
   `sets` (id, box, point, name, folder) et chaque item / entité son `set`.
4. Les [animations](entites.md) (`group=anim`) ne chevauchent jamais deux ensembles.

## Nommer (étape `nommage`, voir [Étapes](etapes.md))
`tools/sk captions ID` → `rpg/pipeline/qa/ID/captions_N.png` : une ligne par ensemble (S<n>, nom actuel,
légende agrandie, premiers sprites). Pas d'OCR : l'agent lit et lance `tools/sk setname ID Sn nom`
(snake_case anglais). `none` = cette ligne n'est pas une légende (crédits, titre). Stocké dans
`overrides.setnames` (ancré sur un point de la légende).
Sans ensemble, `sk captions` montre la légende la plus proche de chaque entité / item (pour `sk name`).

Exemple : Fire-Type Moves R/S (40562) → 16 lignes, 14 attaques (Blast Burn, Blaze Kick, Ember, Eruption,
Fire Blast, Fire Punch, Fire Spin, Flame Wheel, Flamethrower, Heat Wave, Overheat, Sacred Fire, Sunny Day,
Will-o-Wisp) + 2 lignes de crédits (vides).
