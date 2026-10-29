# Sorties et manifests

[← Sommaire](README.md) · voir aussi [Entités](entites.md), [Doublons](doublons.md), [Validation automatique](validation-auto.md)

`tools/sk run ID` réécrit entièrement `rpg/assets/<jeu>/<catégorie>/<titre_feuille>/` :

- **entités** (personnages animés) : `<nom>.png` = bande horizontale des frames, toutes dans des cases de
  même taille (`cell`), alignées (aux pieds ou sur la grille d'origine) ;
- **items isolés** (objets, effets, icônes, frames hors entité) : `<nom>.png`, rognés au plus juste ;
- `manifest.json` ;
- `NON_VERIFIE.txt` si la feuille est `auto_ok`, `A_VERIFIER.txt` si elle n'est pas validée ([Étapes](etapes.md)) ;
- sous-dossiers d'[ensembles](ensembles.md) quand la feuille a des légendes.

Noms automatiques : `<titre>_eNNN` (entités), `<titre>_NNN` (items) ; ou le nom donné par `sk name`.

## manifest.json
```json
{
 "sheet": "8329", "game": "emerald", "category": "characters", "title": "NPCs", "type": "characters",
 "template": "pokemon_ow9",
 "validation": "verified",              // verified | auto | pending
 "entities": [{
   "id": 0, "name": "npcs_e000", "file": "npcs_e000.png", "cell": [16, 21], "zone": null,
   "template": "pokemon_ow9",
   "frames": [{"item": 7, "role": "idle_down", "src": [x,y,w,h], "mirror_of": 2}, ...],
   "box": [x,y,w,h],
   "global_duplicate_of": "emerald/.../x.png"   // posé par sk dupes
 }],
 "items": [{"id": 12, "file": "...png", "x":..,"y":..,"w":..,"h":.., "kind": "sprite",
            "mirror_of": 3, "duplicate_of": 5, "global_mirror_of": "..."}]
}
```
`src` = position dans la feuille brute. `role` vient du gabarit ([Entités](entites.md)). `mirror_of` /
`duplicate_of` : internes à la feuille ; `global_*` : entre feuilles et jeux ([Doublons](doublons.md)).

Le détail complet (items jetés compris) de la dernière exécution est dans `rpg/pipeline/qa/<id>/last_run.json`.
