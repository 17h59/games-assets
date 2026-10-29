# Référence des commandes `sk`

[← Sommaire](README.md) · voir aussi [Paramètres](parametres.md), [Corrections](corrections.md), [Zones](zones.md)

Lancement : `tools/sk <commande> ...` depuis `/home/garen/games` (le lanceur utilise `.venv`). Aide :
`tools/sk -h`, `tools/sk <commande> -h`. Les commandes qui modifient quelque chose sont tracées dans le
[Journal](journal.md) (`MUTATING` dans `cli.py`).

## Consultation
| Commande | Effet |
|---|---|
| `init [--force]` | crée les fiches depuis `rpg/_raw` ([Sources](sources.md)) |
| `list [--game --status --type --category]` | liste les feuilles (`--status` accepte un seul statut) |
| `summary` | compte par type et statut |
| `show ID` | fiche JSON |
| `journal [ID] [--last N]` | historique ([Journal](journal.md)) |
| `report` | [Récapitulatif](recap.md) : avancement %, qui a fait quoi, temps, consommation, reste à faire (écrit aussi `rpg/pipeline/RECAP.txt`) |

## Sprites / personnages
| Commande | Effet |
|---|---|
| `run ID... [-v] [--no-images]` | extrait, écrit les sorties, rapport + planches ([QA](qa.md)) ; cartes : voir plus bas |
| `zoom ID x0,y0,x1,y1 [--scale N]` | planche agrandie d'une zone de la feuille |
| `set ID clé=valeur...` | paramètres ([Paramètres](parametres.md)) ; `valeur=default` retire ; aussi `type= category= status= notes= title=` |
| `drop / keep / split / merge / cut ID n... ` | [Corrections](corrections.md) ; `eN` = toutes les frames de l'entité N |
| `add ID x,y,w,h` / `carve ID x,y,w,h` | boîte forcée / découpe au pixel près |
| `slice ID n cols [rows]` | coupe un item en parts égales |
| `entity ID a b c...` | regroupe des items en une entité |
| `setbox ID Sn x,y,w,h` | rattache une boîte à un ensemble |
| `name ID n|eN nom` | nommer |
| `pixel ID x,y` / `pixel ID x,y,w,h [--top N]` | couleur d'un pixel / couleurs d'un rectangle de l'image source |
| `erase ID x,y,w,h [#RRGGBB...] [--tol N] [--fill clear\|near\|LxH]` | gomme ([Corrections](corrections.md)) |
| `flood ID x,y [--tol N] [--max N]` | rend transparente une région d'une couleur |
| `clear ID drop|keep|merge|split|add|carve|cut|names|erase|flood|all` | effacer des corrections |
| `zone ID x,y,w,h clé=val... | skip` · `zone ID list` · `zone ID del N` | [Zones](zones.md) |
| `status ID statut ["note"]` | [Statuts](statuts.md) (met à jour le marquage de validation) |
| `check ID étape ok|na ["note"]` | confirmer une [étape](etapes.md) |
| `coverage [--game] [--list]` | étapes confirmées / à faire |
| `captions ID` · `setname ID Sn nom` | [ensembles par légende](ensembles.md) : planche, nommage |
| `suggest ID [--apply]` | réglages des feuilles sœurs validées ([Validation auto](validation-auto.md)) |
| `autovalidate [--sample 0.1] [--dry]` | [Validation automatique](validation-auto.md) |
| `regress [--write]` | après une modification de l'outil : feuilles validées dont la sortie change → relecture ; `--write` régénère les autres |
| `dupes` | [Miroirs et doublons](doublons.md) entre toutes les feuilles |

## Cartes / tilesets
| Commande | Effet |
|---|---|
| `run ID` (type map/tileset) | zones de carte, grille de chaque zone, confiance ; planche `regions_*.png` |
| `region ID zN skip|unskip|offset=ox,oy|auto` | corriger une zone de carte |
| `gridcheck ID zN` | 4 décalages candidats côte à côte (planche `gridcheck_zN.png`) |
| `recon ID` | reconstruction d'une seule feuille (aperçus `qa/ID/recon_zN.png`), confirme l'étape si ≥ 97 % |
| `tiles JEU` | référence + bibliothèque de tuiles + cartes en matrices ([Cartes](cartes-tuiles.md)) |
| `objects JEU` | objets des cartes + pages de vérification `obj_<jeu>_NN` ([Objets](objets-cartes.md)) ; développeur |
| `run obj_<jeu>_NN` | reconstruit les objets du jeu + liste et planches de la page |
| `objdrop ID n... [--undo]` / `objsplit ID n x,y,l,h... \| undo` / `objname ID n nom` | corrections d'une page d'objets (numéros de la page, rectangles en tuiles) |
| `run ID` (terrainset) | table d'autotiles PMD → atlas par groupe + voisins ([Terrains PMD](terrains-pmd.md)) |
| `audit --n N` / `audit --report` | tire N feuilles ok validées par Haiku, les renvoie à Gemini (niveau 1) ; rapport accord / désaccord + nature (découpage / regroupement / noms, comparée à la version git) ; `--type` pour auditer les pages (objects, terrainpairs…) ; développeur |
| `run tp_<jeu>_NN` / `tdrop ID n… [--undo]` / `tname ID id nom` | pages de bords de terrains Pokémon (vérification des transitions, noms des terrains) |
| `godot` | catalogue `rpg/godot/catalog.json` pour Godot ([Godot](godot.md)) ; développeur |

**Garde-fous agents** (variable `SK_AGENT=cc:LOT` / `agy:LOT`, posée par le répartiteur) : commandes globales
(`init regress tiles objects autovalidate reference dupes godot`) refusées ; une commande qui modifie une fiche
exige que la fiche soit assignée à CE lot ; `clear ID all` refusé ; `set ID status=` refusé partout (passer par
`sk status`). `check` est refusé si la fiche a changé depuis le dernier `run` (`run_state`).
