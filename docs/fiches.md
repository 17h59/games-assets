# Fiches de feuilles

[← Sommaire](README.md) · voir aussi [Statuts](statuts.md), [Paramètres](parametres.md), [Corrections](corrections.md), [Zones](zones.md)

Une fiche JSON par feuille source : `rpg/pipeline/sheets/<jeu>/<id>.json`. C'est **l'unique interface** de
réglage : l'extraction repart toujours du PNG brut et applique la fiche (déterministe, rien n'est perdu).
On la modifie via `tools/sk` (jamais à la main), ce qui est tracé dans le [Journal](journal.md). Écriture
atomique (`config.write_json_atomic`) : plusieurs agents travaillent en parallèle.

```json
{
 "id": "8329", "game": "emerald", "section": "Non-Playable Characters", "title": "NPCs",
 "src": "_raw/Pokémon Emerald/Non-Playable Characters/NPCs_8329.png",
 "category": "characters",          // characters | monsters | items | effects | ui | tilesets | maps | excluded
 "type": "characters",              // sprites | characters | tileset | map | skip  (quelle chaîne s'applique)
 "status": "ok",                    // voir statuts.md
 "params": {"gap": 0, ...},         // seulement ce qui diffère des défauts (parametres.md)
 "overrides": {                     // corrections manuelles ancrées sur des POINTS de la feuille (corrections.md)
   "drop": [[x,y]], "keep": [], "merge": [[[x,y],[x,y]]], "split": [], "add": [[x,y,w,h]],
   "carve": [[x,y,w,h]], "cut": [], "names": [{"point": [x,y], "name": "old_man"}]
 },
 "zones": [{"box": [x,y,w,h], "params": {...}, "skip": false}],   // zones.md
 "regions": {"cx,cy": {"offset": [ox,oy]} },                      // cartes seulement (cartes-tuiles.md)
 "notes": "...",                    // notes des agents / du développeur (une par ligne)
 "assigned": "20261027_..._b3",     // (temporaire) lot d'agent qui la traite
 "resume": true,                    // travail commencé par un agent puis interrompu : à reprendre
 "attempts": 1                      // tentatives d'agents sans conclusion (delegation.md)
}
```

Pourquoi des points et pas des numéros : les numéros d'items changent dès qu'un paramètre change ; un point
(x, y) de la feuille désigne toujours le même sprite. La CLI convertit les numéros des planches en points.
