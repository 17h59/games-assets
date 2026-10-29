# Corrections manuelles

[← Sommaire](README.md) · code : `extract.apply_overrides`, `_carve` · voir aussi [Fiches](fiches.md)

Stockées dans `overrides` de la fiche, **ancrées sur des points (x, y) de la feuille** (survivent à un
changement de paramètres). La CLI convertit les numéros des planches (`12`, `e3`) en points
(`cli._point_for` : un point qui désigne cet item sans ambiguïté).

| Commande | Effet | Ordre d'application |
|---|---|---|
| `carve ID x,y,w,h` | les pixels opaques du rectangle deviennent UN item, retirés de ceux qui les contenaient (sprites collés au pixel près) | 1 |
| `split ID n` | l'item est re-découpé sans fusion (gap 0) | 2 |
| `add ID x,y,w,h` | tout ce dont le centre est dans la boîte devient un item | 3 |
| `merge ID a b c` | ces items deviennent un seul | 4 |
| `drop ID n / eN` | jeté (`kind=dropped`) | 5 |
| `keep ID n` | récupéré (texte/encart/déchet jeté à tort) | 6 |
| `cut ID n` | personnages : l'item commence une nouvelle entité | 7 |
| `entity ID a b c` | ces items, dans cet ordre, forment UNE entité (retirés des entités automatiques ; une entité réduite à 1 frame redevient un item) | après le regroupement |
| `slice ID n cols [rows]` | ajoute des `carve` qui coupent l'item en parts égales (sprites collés) | = carve |
| `setbox ID Sn x,y,w,h` | les sprites dont le centre est dans la boîte rejoignent l'ensemble Sn | après le rattachement des légendes |
| `name ID n / eN nom` | nom de fichier (snake_case) | 8 |
| `erase ID x,y,w,h [#RRGGBB...] [--tol N] [--fill clear\|near\|LxH]` | gomme : pixels du rectangle (de ces couleurs seulement si données) → transparents (`clear`), ou remplacés AVANT le retrait du fond par le pixel non effacé le plus proche (`near`) ou par le motif décalé d'une période (`16x16`) | 0 (sur l'image) |
| `flood ID x,y [--tol N]` | région d'un seul tenant (4-voisins) de la couleur du point → transparente (fond de panneau, tracé, fond qui troue un sprite) | 0 (sur l'image) |
| `clear ID type|all` | efface une catégorie | — |

**Retouches d'image** (`erase`, `flood`, ajoutées le 2026-10-28, code `imageops.erase_fill` / `post_ops`) :
calculées sur l'image SOURCE (idempotentes), appliquées au fond général ET au fond propre de chaque zone,
avant toute détection. Lire les couleurs avec `sk pixel ID x,y[,w,h]`. Cas prévus : texte du ripper collé à
un sprite (8142, 8367), arcs dessinés (6396), fonds de panneaux (28884), fond qui troue un sprite (6535).

Une correction qui ne trouve rien est listée dans le rapport (« corrections non appliquées »).

**Portée** : `carve` et `split` s'appliquent dans la [zone](zones.md) qui contient leur point (ils ont besoin
des composantes de la zone) ; toutes les autres corrections s'appliquent sur la **feuille entière**, après le
découpage de toutes les zones (un élément peut chevaucher une zone ; une fusion peut réunir deux zones —
l'élément fusionné garde alors directement ses pixels, champ interne `_px`).

Choisir : un défaut **partout** → un [paramètre](parametres.md) ; un défaut **dans une partie** → une
[zone](zones.md) ; un **cas isolé** → une correction.
