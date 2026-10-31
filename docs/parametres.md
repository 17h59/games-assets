# Référence des paramètres

[← Sommaire](README.md) · source de vérité : `DEFAULT_PARAMS` dans `tools/spritekit/config.py`

Une fiche ne stocke que les paramètres qui diffèrent du défaut (`sk set ID clé=valeur`). Une [zone](zones.md)
peut redéfinir n'importe lequel pour son rectangle. Les cartes ont leurs propres défauts (`TILE_PARAMS`
dans `tiles.py` : `bg_mode=edge, bg_tol=0, peel=3, peel_min_area=1024`).

## Fond ([Retrait du fond](fond.md))
| Param | Défaut | Rôle |
|---|---|---|
| `bg` | `auto` | `auto` (couleurs du bord), `none`, `#RRGGBB` ou liste `#A,#B` |
| `bg_tol` | 12 | tolérance par canal |
| `bg_mode` | `global` | `global` (couleur retirée partout) / `edge` (seulement reliée au bord) |
| `black_bg` | false | noir = fond (effets) |
| `peel` | 4 | couches de fonds emboîtés à éplucher ; 0 = off |
| `peel_min_area` | 256 | aire mini d'une zone unie pour être du fond |

## Détection ([Extraction](extraction-sprites.md), [Déchets](dechets.md))
| Param | Défaut | Rôle |
|---|---|---|
| `gap` | 1 | trous ≤ gap px fusionnés (0 = aucun) |
| `min_size` / `min_area` | 4 / 6 | en dessous : `tiny` |
| `drop_text` | true | légendes / encarts jetés |
| `text_max_h` | 16 | hauteur max d'un glyphe |
| `drop_junk` | true | captures 240x160, traits, quadrillages jetés |

## Grille ([Grilles](grilles.md))
| Param | Défaut | Rôle |
|---|---|---|
| `layout` | `auto` | `auto` (grille/xycut si fiable, sinon taches), `grid` (forcer), `blobs` (taches) |
| `block_gap` | 8 | vide séparant deux blocs |
| `grid_min_pitch` / `grid_max_pitch` | 8 / 96 | pas cherché |
| `grid_min_conf` | 0.8 | confiance mini en auto |
| `grid_min_sprites` | 4 | sprites mini par bloc |
| `grid_pitch` | `auto` | pas imposé `LxH` |
| `grid_origin` | `auto` | coin d'une case imposé `x,y` |
| `frag_gap` | 3 | xycut : fragment rattaché s'il est à ≤ frag_gap px |
| `split_own` | false | `sk split` : ne recrée que les morceaux faits des pixels de l'item visé (sinon tout ce qui est dans sa BOÎTE : un split sur un grand cadre dupliquait chaque sprite entouré). Opt-in (2026-10-30, 8183) |
| `split_pieces` | false | pages d'objets : les `objsplit` de la page s'appliquent aussi aux objets issus de la découpe automatique ou d'un autre objsplit (sinon l'objet disparaissait sans morceaux). Opt-in (2026-10-30) |

## Regroupement ([Entités](entites.md))
| Param | Défaut | Rôle |
|---|---|---|
| `group` | `none` | `none`, `rows`, `chunks`, `columns`, `columns_all`, `blocks`, `palette`, `anim` |
| `frames` | 9 | frames par entité (chunks/columns) |
| `frames_alt` | [3] | autres tailles acceptées |
| `entity_shape` | `3x3` | blocks : colonnes x rangées |
| `frame_order` | `row` | blocks : `row` / `col` |
| `col_tol` | 0.5 | même colonne si centres à < col_tol x largeur médiane |
| `row_tol` | 6 | même ligne si bas à ≤ row_tol px |
| `row_split_gap` | 10 | trou qui coupe une ligne |
| `cell` | `auto` | case `LxH`, `auto` (par entité) ou `sheet` (commune) |
| `anchor` | `bottom` | `bottom` (pieds) / `center` |
| `template` | `none` | noms des frames ([Entités](entites.md)) |
| `palette_sim` / `palette_dist` | 0.6 / 48 | group=palette |
| `anim_split_sim` | 0.2 | group=anim : coupe là où les palettes voisines diffèrent plus |
| `sets` | `none` (migration : `captions`) | [ensembles par légende](ensembles.md) |

## Cartes ([Cartes et tuiles](cartes-tuiles.md))
| Param | Défaut | Rôle |
|---|---|---|
| `tile` | 16 | taille de tuile (PMD : 24) |
| `grid_offset` | `auto` | décalage imposé pour toute la feuille |
