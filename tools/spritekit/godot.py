"""Export vers Godot : un catalogue JSON résolu (rpg/godot/catalog.json) que le script GDScript
rpg/godot/tools/build_resources.gd transforme en vraies ressources (SpriteFrames, TileSet à terrains).

Le catalogue ne contient que des chemins res:// et des nombres : Godot n'a rien à deviner.
- entités animées (manifests des feuilles sprites/characters) : bande PNG, taille de case, frames,
  animations nommées (gabarits connus : walk_down…, sinon une animation « default ») ;
- objets des cartes (objects.json, non jetés) ;
- terrains Donjon Mystère (terrains.json) : par groupe, l'atlas et pour chaque tuile les voisins (peering bits).
Chaque entrée garde sa validation (verified / auto / pending) : la démo peut n'utiliser que le vérifié.
"""
import json
import os
from collections import Counter

from . import config, objects, templates

GODOT_DIR = os.path.join(config.PROJECT, "godot")
FPS = {"characters": 6, "effects": 12, "monsters": 8}
# directions des voisins (motif 3x3) -> noms des peering bits Godot (TileSet.CELL_NEIGHBOR_*)
PEERING = {"N": "TOP_SIDE", "NE": "TOP_RIGHT_CORNER", "E": "RIGHT_SIDE", "SE": "BOTTOM_RIGHT_CORNER",
           "S": "BOTTOM_SIDE", "SW": "BOTTOM_LEFT_CORNER", "W": "LEFT_SIDE", "NW": "TOP_LEFT_CORNER"}
# groupes PMD -> terrain de base (les variantes « alt » deviennent des tuiles rares du même terrain)
BASE = [("wall", "walls"), ("ground", "ground"), ("water", "water")]


def res(path):
    return "res://" + os.path.relpath(path, config.PROJECT).replace(os.sep, "/")


def _entities():
    """Une entrée par entité (ses animations : gabarit ou `sk anims`, sinon « default »), plus une entrée
    « feuille » par feuille de personnages/monstres : toutes ses entités comme animations nommées (Zelda : une
    entité = une animation, ex. link_walk_down). Frames = [indice de texture, x, y, l, h]."""
    out = []
    for c in config.all_sheets():
        if c["type"] not in ("sprites", "characters") or c["status"] == "skip":
            continue
        d = config.out_dir(c)
        mp = os.path.join(d, "manifest.json")
        if not os.path.exists(mp):
            continue
        with open(mp, encoding="utf-8") as f:
            man = json.load(f)
        fps = FPS.get(c["category"], 8)
        bundle = {"id": f"{c['game']}/{config.slug(c['title'])}/_feuille", "game": c["game"], "category": c["category"],
                  "sheet": c["id"], "name": "_feuille", "textures": [], "animations": {},
                  "validation": man.get("validation", "pending")}
        for e in man.get("entities", []):
            if not e.get("file") or not e.get("cell") or e.get("global_duplicate_of"):
                continue
            cw, chh = e["cell"]
            roles = [fr.get("role") or f"frame_{i}" for i, fr in enumerate(e["frames"])]
            cells = [[0, i * cw, 0, cw, chh] for i in range(len(roles))]
            anims = {}
            for name, idx in (e.get("animations") or {}).items():  # posées par `sk anims` : prioritaires
                anims[name] = {"frames": [cells[i] for i in idx], "loop": True, "fps": 1 if name.startswith("idle") else fps}
            for name, seq in ({} if anims else templates.ANIMATIONS.get(e.get("template") or "none", {})).items():
                idx = [roles.index(r) for r in seq if r in roles]
                if idx:
                    anims[name] = {"frames": [cells[i] for i in idx], "loop": True, "fps": 1 if name.startswith("idle") else fps}
            if not anims:
                anims["default"] = {"frames": cells, "loop": True, "fps": fps}
            tex = res(os.path.join(d, e["file"]))
            out.append({"id": f"{c['game']}/{config.slug(c['title'])}/{e['name']}", "game": c["game"],
                        "category": c["category"], "sheet": c["id"], "name": e["name"], "textures": [tex],
                        "cell": e["cell"], "roles": roles, "animations": anims,
                        "validation": man.get("validation", "pending"),
                        "flip_for_right": "walk_left" in anims and "walk_right" not in anims})
            if c["category"] in ("characters", "monsters") or c["type"] == "characters":
                k = len(bundle["textures"])
                bundle["textures"].append(tex)
                for name, a in anims.items():
                    key = e["name"] if name == "default" else f"{e['name']}_{name}"
                    bundle["animations"][key] = dict(a, frames=[[k] + fr[1:] for fr in a["frames"]])
        if bundle["animations"]:
            out.append(bundle)
    return out


def _objects():
    out = []
    for game in config.GAMES.values():
        p = os.path.join(config.ASSETS, game, "objects", "objects.json")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            cat = json.load(f)
        pages = {}
        for pg in objects.pages(game):
            for s in pg["regions"]["sigs"]:
                pages[s] = "verified" if pg["status"] == "ok" else "pending"
        for o in cat["objects"]:
            if o.get("dropped") or o["kind"] == "terrain_piece":
                continue
            out.append({"id": f"{game}/{o['name']}", "game": game, "kind": o["kind"], "size_tiles": o["size"],
                        "tile": cat["tile"], "texture": res(os.path.join(config.ASSETS, game, "objects", o["name"] + ".png")),
                        "count": o["count"], "validation": pages.get(o["sig"], "pending")})
    return out


def _terrains():
    out = []
    root = os.path.join(config.ASSETS, "pmd_red", "terrains")
    status = {c["id"]: c["status"] for c in config.all_sheets() if c["type"] == "terrainset"}
    for d in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        p = os.path.join(root, d, "terrains.json")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            t = json.load(f)
        groups = []
        for g in t["groups"]:
            base = next((b for key, b in BASE if key in g["name"]), None)
            if base is None or "sparkle" in g["name"] or "unused" in g["name"]:  # calque de reflets : pas un terrain
                continue
            tiles = []
            for tl in g["tiles"]:
                if not tl["mask"]:
                    continue
                tiles.append({"col": tl["col"], "row": tl["row"],
                              "peering": [PEERING[k] for k, v in tl["mask"].items() if v]})
            groups.append({"name": g["name"], "terrain": base, "alt": g["name"] != base,
                           "texture": res(os.path.join(root, d, g["file"])), "tiles": tiles})
        out.append({"id": d, "title": t["title"], "sheet": t["sheet"], "tile": t["tile"], "groups": groups,
                    "validation": "verified" if status.get(t["sheet"]) == "ok" else "pending"})
    return out


def _poke_terrains():
    """Bords de terrains Pokémon (terrains.json de terrains.py) : tuiles pures (terrain sur les 8 voisins) +
    transitions gardées (non jetées) par les pages de vérification tp_<jeu>_NN. Un TileSet à terrains par jeu."""
    out = []
    status = {}
    for c in config.all_sheets():
        if c["type"] == "terrainpairs":
            status.setdefault(c.get("game"), []).append(c["status"])
    for game in config.GAMES.values():
        p = os.path.join(config.ASSETS, game, "terrains", "terrains.json")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            t = json.load(f)
        kept = [x for x in t["transitions"] if not x.get("dropped")]
        if not kept:
            continue
        used = {x["center"] for x in kept} | {v for x in kept for v in x["peering"].values()}
        terrs = [x for x in t["terrains"] if x["id"] in used]
        index = {x["id"]: i for i, x in enumerate(terrs)}
        names = []
        for x in terrs:  # noms en double (deux « sand ») : suffixe = identifiant d'origine
            n = x["name"]
            names.append(n if [y["name"] for y in terrs].count(n) == 1 else f"{n}_{x['id']}")
        tiles = []
        for x in terrs:
            top = max(tl["count"] for tl in x["tiles"])
            for tl in x["tiles"]:  # probabilité = fréquence dans les cartes (les variantes rares restent rares)
                tiles.append({"col": tl["pos"][0], "row": tl["pos"][1], "terrain": index[x["id"]],
                              "probability": round(tl["count"] / top, 3),
                              "peering": {b: index[x["id"]] for b in PEERING.values()}})
        for x in kept:
            tiles.append({"col": x["pos"][0], "row": x["pos"][1], "terrain": index[x["center"]],
                          "peering": {PEERING[k]: index[v] for k, v in x["peering"].items()}})
        sts = status.get(game, [])
        out.append({"id": game, "tile": t["tile"], "texture": res(os.path.join(config.ASSETS, game, "terrains", t["atlas"])),
                    "terrains": [{"name": n, "color": x["color"]} for n, x in zip(names, terrs)],
                    # paires classées par nombre de bords gardés (les plus complètes d'abord)
                    "pairs": [list(p) for p, _ in Counter(tuple(sorted((index[x["center"]], index[v])))
                                                          for x in kept for v in set(x["peering"].values())
                                                          if v != x["center"]).most_common()],
                    "tiles": tiles,
                    "validation": "verified" if sts and all(s == "ok" for s in sts) else "pending"})
    return out


def _tilemaps():
    """Bibliothèques de tuiles (une TileSet par jeu, une source par page d'atlas) et cartes à reconstruire
    en TileMapLayer (les grilles restent dans les region_N.json, lus par le script Godot)."""
    libs, maps = {}, []
    status = {c["id"]: (c["type"], c["status"]) for c in config.all_sheets()}
    for game in config.GAMES.values():
        base = os.path.join(config.ASSETS, game, "tiles")
        p = os.path.join(base, "library.json")
        if not os.path.exists(p):
            continue
        with open(p) as f:
            lib = json.load(f)
        npages = max(e["page"] for e in lib["tiles"]) + 1
        # tuiles solides (collision) : tout ce qui n'est pas du sol d'après les objets (bâtiments, murs, meubles,
        # arbres) ; l'eau reste traversable (pas distinguée du sol). Heuristique, voir docs/godot.md.
        solid = []
        op = os.path.join(config.ASSETS, game, "objects", "objects.json")
        if os.path.exists(op):
            with open(op) as f:
                ob = json.load(f)
            ground = set(ob.get("terrain", []))
            solid = [i for i in range(len(lib["tiles"])) if i not in ground]
        libs[game] = {"tile": lib["tile"], "pages": [res(os.path.join(base, f"atlas_{k}.png")) for k in range(npages)],
                      "tiles": [[e["page"], e["col"], e["row"]] for e in lib["tiles"]], "solid": solid}
        root = os.path.join(config.ASSETS, game, "maps")
        for d in sorted(os.listdir(root)) if os.path.isdir(root) else []:
            for f in sorted(os.listdir(os.path.join(root, d))):
                if f.startswith("region_") and f.endswith(".json"):
                    with open(os.path.join(root, d, f)) as fh:
                        g = json.load(fh)
                    ty, st = status.get(str(g["sheet"]), ("map", "?"))
                    if ty != "map" or st == "skip":
                        continue
                    maps.append({"id": f"{game}/{d}_r{g['region']}", "game": game, "title": g.get("title"),
                                 "json": res(os.path.join(root, d, f)), "cols": g["cols"], "rows": g["rows"],
                                 "validation": "verified" if st == "ok" else "pending"})
    return libs, maps


def export():
    os.makedirs(GODOT_DIR, exist_ok=True)
    libs, maps = _tilemaps()
    cat = {"entities": _entities(), "objects": _objects(), "terrains": _terrains(),
           "poke_terrains": _poke_terrains(), "tile_libraries": libs, "maps": maps}
    config.write_json_atomic(os.path.join(GODOT_DIR, "catalog.json"), cat)
    return {k: len(v) for k, v in cat.items()}
