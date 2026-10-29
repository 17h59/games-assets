"""Terrains et bords de terrains (autotiles Godot) déduits des cartes Pokémon / Minish Cap.

1. Tuiles PURES : tuiles de terrain (voir objects.classify_terrain : texture répétée, fréquente) ;
2. TERRAINS : groupes de tuiles pures voisines dans les cartes et de couleur moyenne proche (herbe et ses
   variantes = un terrain) ;
3. TRANSITIONS : une tuile non pure dont chaque pixel est égal, à la même position, à l'une de DEUX tuiles
   pures A ou B (au moins `cover` des pixels) : c'est un bord entre A et B (les textures GBA sont alignées sur
   la grille) ;
4. VOISINS : la tuile est coupée en 3x3 parties (coins, côtés, centre) ; chaque partie appartient au terrain
   majoritaire dans ses pixels -> centre = terrain de la tuile, 8 parties = peering bits d'un terrain Godot
   (mode coins + côtés).
Sorties : rpg/assets/<jeu>/terrains/terrains.json + atlas.png (tuiles pures et transitions seulement) +
planche QA rpg/pipeline/qa/terrains_<jeu>/.
"""
import json
import os
from collections import Counter, defaultdict

import numpy as np
from PIL import Image, ImageDraw

from . import config, objects

PARTS = [("NW", 0, 0), ("N", 0, 1), ("NE", 0, 2), ("W", 1, 0), ("C", 1, 1), ("E", 1, 2),
         ("SW", 2, 0), ("S", 2, 1), ("SE", 2, 2)]


def _bounds(t):
    a = t // 3
    return [(0, a), (a, t - a), (t - a, t)]


def pure_tiles(lib, pair, min_count=8, self_ratio=0.15):
    """Texture qui se répète elle-même dans les DEUX directions (herbe, sable, eau, parquet). Plus strict que
    classify_terrain (qui garde aussi les tuiles aux voisins variés, dont les bords eux-mêmes)."""
    tot = {">": Counter(), "v": Counter()}
    selfc = {">": Counter(), "v": Counter()}
    for (a, d, b), c in pair.items():
        if d in (">", "v"):
            tot[d][a] += c
            if a == b:
                selfc[d][a] += c
    out = []
    for i, e in enumerate(lib["tiles"]):
        if e["count"] >= min_count and selfc[">"][i] / max(1, tot[">"][i]) >= self_ratio \
                and selfc["v"][i] / max(1, tot["v"][i]) >= self_ratio:
            out.append(i)
    return out


def _cluster(pure, pair, pixels, max_dist=48.0, min_adj=2, same_dist=14.0):
    """Union des tuiles pures voisines dans les cartes (>= min_adj fois) et de couleur moyenne proche, ou de
    couleur moyenne presque identique (variantes d'une même texture)."""
    mean = {i: pixels(i)[..., :3].reshape(-1, 3).mean(0) for i in pure}
    parent = {i: i for i in pure}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for (a, d, b), c in pair.items():
        if a in parent and b in parent and a != b and c >= min_adj and np.linalg.norm(mean[a] - mean[b]) <= max_dist:
            parent[find(a)] = find(b)
    keys = list(pure)
    M = np.array([mean[i] for i in keys])
    for x in range(len(keys)):
        close = np.nonzero(np.linalg.norm(M[x + 1:] - M[x], axis=1) <= same_dist)[0]
        for y in close:
            parent[find(keys[x])] = find(keys[x + 1 + y])
    groups = defaultdict(list)
    for i in pure:
        groups[find(i)].append(i)
    return list(groups.values()), mean


PAIRS_PER_PAGE = 6


def page_id(game, n):
    return f"tp_{game}_{n:02d}"


def pages(game):
    d = os.path.join(config.SHEETS, game)
    return [config._read_json(os.path.join(d, f)) for f in sorted(os.listdir(d)) if f.startswith("tp_") and f.endswith(".json")] \
        if os.path.isdir(d) else []


def _decisions(game):
    drop, names = set(), {}
    for c in pages(game):
        drop |= set(c.get("overrides", {}).get("drop", []))
        names.update(c.get("overrides", {}).get("names", {}))
    return drop, names


def build(game, cover=0.6, min_part=0.1, min_count=2):
    lib, pixels = objects.load_library(game)
    t = lib["tile"]
    grids = objects.load_grids(game)
    pair = objects.neighbor_stats(grids)
    terrain, walls = objects.classify_terrain(lib, pair)
    pure = pure_tiles(lib, pair)
    clusters, mean = _cluster(pure, pair, pixels)
    clusters.sort(key=lambda g: -sum(lib["tiles"][i]["count"] for i in g))
    tid = {i: k for k, g in enumerate(clusters) for i in g}
    pure_px = {i: pixels(i)[..., :3] for i in pure}
    # voisins purs de chaque tuile (candidats A, B)
    nb = defaultdict(Counter)
    for (a, d, b), c in pair.items():
        if b in tid:
            nb[a][b] += c
    bounds = _bounds(t)
    # sols unis (1-2 couleurs : blanc, noir, vide) : ils « expliquent » n'importe quel pixel de leur couleur ->
    # fausses transitions (meubles posés sur un sol uni). Exclus comme référence.
    flat = {i for i in pure_px if len(np.unique(pure_px[i].reshape(-1, 3), axis=0)) <= 2}
    pure_px = {i: v for i, v in pure_px.items() if i not in flat}
    pure_ids = list(pure_px)
    PURE = np.stack([pure_px[k] for k in pure_ids]) if pure_ids else None
    transitions = []
    for i, e in enumerate(lib["tiles"]):
        if i in tid or e["count"] < min_count or i in walls:
            continue
        px = pixels(i)
        # candidats : sols purs voisins dans les cartes + les 6 sols purs qui expliquent le plus de pixels
        sc = (PURE == px[..., :3]).all(-1).reshape(len(pure_ids), -1).mean(1)
        cands = list(dict.fromkeys([b for b, _ in nb[i].most_common(8) if b in pure_px]
                                   + [pure_ids[k] for k in np.argsort(sc)[-6:] if sc[k] > 0.05]))
        if len(cands) < 2:
            continue
        if (px[..., 3] < 255).any():
            continue
        rgb = px[..., :3]
        eq = {b: (rgb == pure_px[b]).all(-1) for b in cands}
        best = None
        for ai, a in enumerate(cands):
            for b in cands[ai + 1:]:
                if tid[a] == tid[b]:
                    continue
                ma, mb = eq[a], eq[b]
                cov = (ma | mb).mean()
                if cov >= cover and ma.mean() >= min_part and mb.mean() >= min_part and (best is None or cov > best[0]):
                    best = (cov, a, b)
        if best is None:
            continue
        cov, a, b = best
        ma, mb = eq[a], eq[b]
        owner = {}
        for name, r, c in PARTS:
            (y0, y1), (x0, x1) = bounds[r], bounds[c]
            na, nbb = int(ma[y0:y1, x0:x1].sum()), int(mb[y0:y1, x0:x1].sum())
            owner[name] = tid[a] if na >= nbb else tid[b]
        if len(set(owner.values())) < 2:
            continue  # tuile « pure » d'un terrain avec un peu de l'autre : pas un bord
        transitions.append({"tile": i, "hash": e["hash"], "count": e["count"], "cover": round(float(cov), 3), "pair": sorted([tid[a], tid[b]]),
                            "center": owner["C"], "peering": {k: v for k, v in owner.items() if k != "C"}})
    # atlas : tuiles pures puis transitions, 32 colonnes
    keep = [i for g in clusters for i in g] + [tr["tile"] for tr in transitions]
    cols = 32
    rows = (len(keep) + cols - 1) // cols
    atlas = np.zeros((rows * t, cols * t, 4), np.uint8)
    pos = {}
    for k, i in enumerate(keep):
        r, c = divmod(k, cols)
        atlas[r * t:(r + 1) * t, c * t:(c + 1) * t] = pixels(i)
        pos[i] = [c, r]
    out = os.path.join(config.ASSETS, game, "terrains")
    os.makedirs(out, exist_ok=True)
    Image.fromarray(atlas).save(os.path.join(out, "atlas.png"))
    drop, names = _decisions(game)
    terrains = []
    for k, g in enumerate(clusters):
        col = np.mean([mean[i] for i in g], 0)
        nm = next((names[lib["tiles"][i]["hash"]] for i in g if lib["tiles"][i]["hash"] in names), f"terrain_{k}")
        terrains.append({"id": k, "name": nm, "color": [int(x) for x in col], "key": lib["tiles"][g[0]]["hash"],
                         "tiles": [{"tile": i, "pos": pos[i], "count": lib["tiles"][i]["count"]} for i in g]})
    for tr in transitions:
        tr["dropped"] = tr["hash"] in drop
    for tr in transitions:
        tr["pos"] = pos[tr["tile"]]
    pairs = Counter(tuple(tr["pair"]) for tr in transitions)
    res = {"game": game, "tile": t, "atlas": "atlas.png", "cols": cols, "terrains": terrains,
           "transitions": transitions, "pairs": {f"{a}-{b}": n for (a, b), n in pairs.most_common()}}
    config.write_json_atomic(os.path.join(out, "terrains.json"), res)
    _assign_pages(game, [f"{a}-{b}" for (a, b), _ in pairs.most_common()], {t["id"]: t["key"] for t in terrains})
    return {"terrains": len(terrains), "tuiles_pures": len(pure), "transitions": len(transitions),
            "paires": len(pairs)}


def _assign_pages(game, pair_keys, keys):
    """Pages STABLES de paires (clé de paire = hash des tuiles représentatives des deux terrains)."""
    def pk(p):
        a, b = map(int, p.split("-"))
        return "|".join(sorted([keys[a], keys[b]]))
    existing = {c["id"]: c for c in pages(game)}
    where = {k: pid for pid, c in existing.items() for k in c["regions"]["pairs"]}
    new = {pid: [] for pid in existing}
    n = len(existing)
    for p in pair_keys:
        k = pk(p)
        pid = where.get(k)
        if pid is None:
            last = page_id(game, n - 1) if n else None
            if last is None or len(new[last]) >= PAIRS_PER_PAGE:
                last = page_id(game, n); n += 1
                existing[last] = {"id": last, "game": game, "section": "terrains", "title": f"Bords de terrains {game} {last[-2:]}",
                                  "src": None, "category": "terrain_edges", "type": "terrainpairs", "status": "todo",
                                  "params": {}, "overrides": {"drop": [], "names": {}}, "regions": {"pairs": []}, "notes": ""}
                new[last] = []
            pid = last
        new[pid].append(k)
    for pid, c in existing.items():
        got = new.get(pid, [])
        sigs = [x for x in c["regions"]["pairs"] if x in got] + [x for x in got if x not in c["regions"]["pairs"]]
        if sigs != c["regions"]["pairs"] or not os.path.exists(config.sheet_path(game, pid)):
            if os.path.exists(config.sheet_path(game, pid)):
                c = config.load(pid)
            c["regions"] = {"pairs": sigs}
            config.save(c)


def page_pairs(cfg):
    """[(n, a, b, [transitions])] pour une page (numéros de transition 1..N sur toute la page)."""
    with open(os.path.join(config.ASSETS, cfg["game"], "terrains", "terrains.json")) as f:
        res = json.load(f)
    bykey = {t["key"]: t["id"] for t in res["terrains"]}
    out, n = [], 0
    for k in cfg["regions"]["pairs"]:
        ka, kb = k.split("|")
        if ka not in bykey or kb not in bykey:
            continue
        a, b = sorted([bykey[ka], bykey[kb]])
        trs = [tr for tr in res["transitions"] if tr["pair"] == [a, b]]
        rows = []
        for tr in trs:
            n += 1
            rows.append((n, tr))
        out.append((a, b, rows))
    return res, out


def montage_page(cfg, scale=3):
    """Planche d'une page : une rangée par paire (tuile pure A, tuile pure B, puis chaque bord numéroté avec,
    à droite, le terrain de chaque partie : couleur de A ou de B ; jetés barrés)."""
    from .qa import _font
    res, rows = page_pairs(cfg)
    base = os.path.join(config.ASSETS, cfg["game"], "terrains")
    atlas = Image.open(os.path.join(base, "atlas.png")).convert("RGBA")
    t = res["tile"]
    terr = {x["id"]: x for x in res["terrains"]}
    font = _font(13)
    cell = t * scale + 34
    W = 1000
    per = (W - 10) // cell
    lines = []
    for a, b, trs in rows:
        items = [("A " + terr[a]["name"], terr[a]["tiles"][0]["pos"], None, None),
                 ("B " + terr[b]["name"], terr[b]["tiles"][0]["pos"], None, None)] + [(f"#{n}", tr["pos"], tr, n) for n, tr in trs]
        for k in range(0, len(items), per):
            lines.append(items[k:k + per])
    H = len(lines) * (cell + 8) + 10
    sheet = Image.new("RGBA", (W, max(H, 40)), (50, 50, 60, 255))
    d = ImageDraw.Draw(sheet)
    y = 6
    for items in lines:
        x = 6
        for lab, (c, r), tr, n in items:
            tile = atlas.crop((c * t, r * t, (c + 1) * t, (r + 1) * t)).resize((t * scale, t * scale), Image.NEAREST)
            sheet.alpha_composite(tile, (x, y + 16))
            d.text((x, y), lab[:14], fill=(255, 255, 120) if tr is None else (220, 220, 220), font=font)
            if tr:
                for name, r_, c_ in PARTS:
                    v = tr["center"] if name == "C" else tr["peering"][name]
                    col = (255, 80, 80) if v == tr["pair"][0] else (80, 160, 255)
                    d.rectangle((x + t * scale + 3 + c_ * 7, y + 16 + r_ * 7, x + t * scale + 8 + c_ * 7, y + 21 + r_ * 7), fill=col)
                if tr.get("dropped"):
                    d.line((x, y + 16, x + t * scale, y + 16 + t * scale), fill=(255, 60, 60), width=3)
            x += cell
        y += cell + 8
    out = os.path.join(config.QA_DIR, cfg["id"])
    os.makedirs(out, exist_ok=True)
    p = os.path.join(out, "bords_0.png")
    sheet.save(p)
    return [p]


def page_report(cfg):
    res, rows = page_pairs(cfg)
    terr = {x["id"]: x for x in res["terrains"]}
    lines = [f"{cfg['id']} : {len(rows)} paire(s) de terrains — statut {cfg['status']}",
             "  carrés à droite de chaque bord : ROUGE = partie du terrain A, BLEU = partie du terrain B"]
    for a, b, trs in rows:
        lines.append(f"  A = {terr[a]['name']} (id {a})  /  B = {terr[b]['name']} (id {b}) : bords "
                     + " ".join(f"#{n}{'(jeté)' if tr.get('dropped') else ''}" for n, tr in trs))
    return "\n".join(lines)


def montage(game, max_pairs=40, scale=2):
    """Planche : pour chaque paire de terrains (les plus fournies d'abord), une tuile pure de chaque côté puis
    ses transitions, avec le terrain du centre et des 8 voisins en petit (couleur moyenne du terrain)."""
    from .qa import _font
    base = os.path.join(config.ASSETS, game, "terrains")
    with open(os.path.join(base, "terrains.json")) as f:
        res = json.load(f)
    atlas = Image.open(os.path.join(base, "atlas.png")).convert("RGBA")
    t = res["tile"]
    col = {tr["id"]: tuple(tr["color"]) for tr in res["terrains"]}
    rep = {tr["id"]: tr["tiles"][0]["pos"] for tr in res["terrains"]}
    by_pair = defaultdict(list)
    for tr in res["transitions"]:
        by_pair[tuple(tr["pair"])].append(tr)
    font = _font(12)
    rows = sorted(by_pair.items(), key=lambda kv: -len(kv[1]))[:max_pairs]
    cell = t * scale + 14
    W = 1400
    lines = []
    for (a, b), trs in rows:
        n = len(trs) + 2
        per = (W - 120) // cell
        for k in range(0, n, per):
            lines.append(((a, b), trs, k, per))
    H = len(lines) * (cell + 18) + 10
    sheet = Image.new("RGBA", (W, max(H, 40)), (50, 50, 60, 255))
    d = ImageDraw.Draw(sheet)

    def tile(pos):
        c, r = pos
        return atlas.crop((c * t, r * t, (c + 1) * t, (r + 1) * t)).resize((t * scale, t * scale), Image.NEAREST)
    y = 6
    for (a, b), trs, k, per in lines:
        if k == 0:
            d.text((4, y + 4), f"{a} / {b}", fill=(255, 255, 120), font=font)
        items = [("A", rep[a], None), ("B", rep[b], None)] + [(str(tr["tile"]), tr["pos"], tr) for tr in trs]
        x = 110
        for lab, pos, tr in items[k:k + per]:
            sheet.alpha_composite(tile(pos), (x, y + 14))
            d.text((x, y), lab, fill=(200, 200, 200), font=font)
            if tr:
                for name, r_, c_ in PARTS:
                    v = tr["center"] if name == "C" else tr["peering"][name]
                    d.rectangle((x + t * scale + 1 + c_ * 4, y + 14 + r_ * 4, x + t * scale + 4 + c_ * 4, y + 17 + r_ * 4), fill=col[v])
            x += cell
        y += cell + 18
    outd = os.path.join(config.QA_DIR, f"terrains_{game}")
    os.makedirs(outd, exist_ok=True)
    paths = []
    for k, py in enumerate(range(0, sheet.height, 1400)):
        p = os.path.join(outd, f"terrains_{k}.png")
        sheet.crop((0, py, W, min(sheet.height, py + 1400))).save(p)
        paths.append(p)
    return paths
