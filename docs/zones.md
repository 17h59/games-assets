# Zones

[← Sommaire](README.md) · code : `extract.parts_of`, `_filter_overrides`, `detect` · commande : `sk zone`

Idée de l'utilisateur : une feuille mélange souvent plusieurs mises en page ; au lieu d'un compromis global,
on la découpe en **zones** rectangulaires, chacune avec ses propres [paramètres](parametres.md).

```
tools/sk zone ID x,y,w,h layout=grid grid_pitch=16x32 frames=9 template=pokemon_ow9
tools/sk zone ID x,y,w,h group=blocks entity_shape=3x3 template=pokemon_ow9_grid
tools/sk zone ID x,y,w,h bg=#0D6AAB bg_mode=edge peel=4     # fond propre à la zone
tools/sk zone ID x,y,w,h skip                               # ignorée (crédits, captures, schémas)
tools/sk zone ID list        tools/sk zone ID del N
```

- Coordonnées de la feuille brute (lisibles sur l'overview). Stockées dans `zones` de la [fiche](fiches.md).
- Priorité dans l'ordre de création : un pixel appartient à la première zone qui le contient ; le reste
  de la feuille garde les réglages globaux.
- Chaque zone est traitée comme une partie indépendante ([Extraction](extraction-sprites.md)) : ses
  propres composantes, grille, regroupement en entités.
- **Fond par zone** : si la zone a un paramètre de fond (`bg bg_tol bg_mode black_bg peel peel_min_area`),
  le retrait du fond est refait sur le seul rectangle, avec `bg_mode=edge` relatif au bord de la zone.
- Les [corrections](corrections.md) s'appliquent à la partie qui contient leur point.
- Overview : cadres cyan `Z0`, `Z1`... ; rapport : ligne `zones :`.

Exemple validé : icônes de types R/S (64357), zones `0,0,128,96` grille 32x16 et `0,96,128,16` grille 32x8
→ 23 badges + 7 icônes. Frontier Brains (8331) : zone du haut en `group=blocks` 3x3 → 7 personnages.
