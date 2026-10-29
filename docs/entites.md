# Regroupement en entités

[← Sommaire](README.md) · code : `extract.group_entities`, `group_columns`, `group_blocks`, `group_by_palette`, `layout_frames`, `check_palettes` · `templates.py`

Une **entité** = un personnage / monstre / animation : ses frames dans une bande horizontale, cases de même
taille ([Sorties](sorties.md)).

## Modes (`group`)
- `none` : pas d'entité, items isolés (objets, icônes).
- `chunks` : lignes coupées en segments (trou > `row_split_gap`, ou case vide en grille), puis chaque
  segment découpé en paquets de tailles `frames`/`frames_alt` : **le moins de paquets possible**, et à égalité
  là où les écarts sont les plus grands (`_partition`) ; ex. 6 = 3+3, 12 = 9+3.
- `rows` : un segment de ligne entier = une entité.
- `columns` : idem en colonnes (frames de haut en bas) ; colonnes = centres à < `col_tol` x largeur
  médiane ; `columns_all` = colonne entière.
- `blocks` : blocs 2D de `entity_shape` cases (ex. `3x3`), d'après les indices de rangée et de colonne ;
  frames lues `frame_order=row` ou `col`.
- `anim` : animations (effets, monstres, persos Zelda) : segments de ligne coupés aux trous puis là où la
  palette change (Jaccard < `anim_split_sim`) ; groupes d'1 frame = items isolés ; respecte les
  [ensembles](ensembles.md).
- `palette` : sprites proches (≤ `palette_dist`) dont les palettes se ressemblent (Jaccard ≥ `palette_sim`) ;
  pour les feuilles Zelda en vrac.

`cut` ([Corrections](corrections.md)) force le début d'une nouvelle entité.

## Alignement (`layout_frames`)
Cases de grille : la position dans la case est l'alignement d'origine (vide commun rogné). Sinon
`anchor=bottom` : pieds alignés, et si les frames suivent un pas régulier on garde leur décalage d'origine
(pas de tremblement) ; `center` ; `cell` impose la taille.

## Gabarits (`template`) → rôles des frames
- `pokemon_ow9` : idle_down, idle_up, idle_left, walk_down_1, walk_down_2, walk_up_1, walk_up_2, walk_left_1, walk_left_2
- `pokemon_ow9_grid` : même chose en bloc 3x3 lu ligne par ligne (rangée 2 = 1er pas, 3 = 2e pas)
- `pokemon_ow3` : 3 poses fixes
- Animations Godot prévues (`ANIMATIONS`) : walk_X = [pas 1, repos, pas 2, repos] ; la droite = gauche
  retournée (`flip_h`).
Défaut d'`init` pour les persos Émeraude / R-S : `group=chunks frames=9 template=pokemon_ow9`.

## Contrôle de palette (`mixed_entity`)
Une frame dont < 50 % des couleurs se retrouvent dans les autres frames de l'entité → anomalie : deux
personnages probablement mélangés.
