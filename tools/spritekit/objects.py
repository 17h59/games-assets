"""Objets des cartes (maisons, arbres, meubles, panneaux) reconstitués à partir des tuiles.

Principe :
1. terrain = tuiles fréquentes qui côtoient beaucoup de voisins différents ou se répètent elles-mêmes
   (herbe, sable, parquet, eau) ; murs = tuiles collées au vide (bord des pièces) ou bandes horizontales
   répétées : ce sont des SÉPARATEURS (jamais dans un objet, jamais pris comme sol) ;
2. un objet = composante connexe de tuiles non-terrain voisines, dans une zone de carte ;
3. les objets de même disposition sont fusionnés (une maison présente 5 fois = 1 objet, 5 occurrences) ;
4. le sol sous l'objet est retiré pixel par pixel, TUILE PAR TUILE, en le comparant aux tuiles de terrain
   voisines (alignées sur la grille : la texture du sol tombe exactement au même endroit) ;
5. l'ombre (pixels = sol assombri uniformément, d'un seul tenant avec le vide) devient du noir
   semi-transparent : l'objet se pose sur n'importe quel sol ;
6. vérification : les objets sont répartis en PAGES stables (fiches de type « objects »,
   `obj_<jeu>_NN`) ; les corrections (jeter, nommer, découper) sont rangées par signature dans la fiche
   de la page, donc l'empreinte d'état de la page change quand on la corrige.
Feuilles de type tileset (tuiles rangées à plat) et feuilles ignorées : exclues.
"""
import hashlib
import json
import os
from collections import Counter, defaultdict

import numpy as np
from PIL import Image
from scipy import ndimage

from . import config

DIRS = {">": (0, 1), "v": (1, 0)}
PAGE = 40  # objets par page de vérification
SHADOW_K = (0.3, 0.92)  # assombrissement accepté pour une ombre (valeur / sol)
SHADOW_SPREAD = 0.12    # écart max entre canaux (une ombre assombrit R, G, B du même facteur)


def load_library(game):
    base = os.path.join(config.ASSETS, game, "tiles")
    with open(os.path.join(base, "library.json")) as f:
        lib = json.load(f)
    pages = {}
    t = lib["tile"]

    def pixels(i):
        e = lib["tiles"][i]
        if e["page"] not in pages:
            pages[e["page"]] = np.array(Image.open(os.path.join(base, f"atlas_{e['page']}.png")).convert("RGBA"))
        pg = pages[e["page"]]
        return pg[e["row"] * t:(e["row"] + 1) * t, e["col"] * t:(e["col"] + 1) * t]

    return lib, pixels


def _sheet_types(game):
    out = {}
    d = os.path.join(config.SHEETS, game)
    for f in os.listdir(d) if os.path.isdir(d) else []:
        if f.endswith(".json") and not f.startswith(".tmp_"):
            c = config._read_json(os.path.join(d, f))
            out[str(c["id"])] = (c["type"], c["status"])
    return out


def load_grids(game, maps_only=True):
    """Grilles des zones de cartes. maps_only : sans les feuilles de type tileset (tuiles rangées à
    plat, pas des cartes : leurs voisinages sont faux) ni les feuilles ignorées."""
    root = os.path.join(config.ASSETS, game, "maps")
    types = _sheet_types(game) if maps_only else {}
    out = []
    for d in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        for f in sorted(os.listdir(os.path.join(root, d))):
            if f.startswith("region_") and f.endswith(".json"):
                with open(os.path.join(root, d, f)) as fh:
                    g = json.load(fh)
                ty, st = types.get(str(g.get("sheet")), ("map", "ok"))
                if maps_only and (ty == "tileset" or st == "skip"):
                    continue
                g["grid"] = np.array(g["grid"], dtype=np.int32)
                g["dir"] = d
                out.append(g)
    return out


def neighbor_stats(grids):
    """c[(a, d, b)] : nb de fois où b est le voisin de a dans la direction d (>, v, <, ^)."""
    pair = Counter()
    for g in grids:
        G = g["grid"]
        for d, (dy, dx) in DIRS.items():
            A = G[:G.shape[0] - dy, :G.shape[1] - dx]
            B = G[dy:, dx:]
            m = (A >= 0) & (B >= 0)
            for a, b in zip(A[m].tolist(), B[m].tolist()):
                pair[(a, d, b)] += 1
                pair[(b, "<" if d == ">" else "^", a)] += 1
    return pair


def classify_terrain(lib, pair, min_count=8, self_ratio=0.15, min_neighbors=10, wall_min_count=12):
    """Terrain = texture qui se répète dans les DEUX directions (herbe, sol, eau, parquet),
    ou tuile très fréquente aux voisins très variés. Un mur ou un toit ne se répète
    qu'horizontalement : ce n'est pas du terrain, c'est un morceau d'objet.
    Renvoie (terrain, murs) : les murs/clôtures sont des séparateurs, pas un sol."""
    tot = {">": Counter(), "v": Counter()}
    selfc = {">": Counter(), "v": Counter()}
    nbs = defaultdict(set)
    for (a, d, b), c in pair.items():
        if d in DIRS:
            tot[d][a] += c
            if a == b:
                selfc[d][a] += c
        nbs[a].add(b)
    # rigidité : directions où le voisin le plus fréquent revient >= 60 % du temps. Un morceau de bâtiment
    # (Centre Pokémon présent dans toutes les villes) a des voisins rigides ; un sol, non.
    top, tot4 = Counter(), Counter()
    for (a, d, b), c in pair.items():
        tot4[(a, d)] += c
        top[(a, d)] = max(top[(a, d)], c)
    terrain, walls = set(), set()
    for i, e in enumerate(lib["tiles"]):
        if e["count"] < min_count:
            continue
        rh = selfc[">"][i] / max(1, tot[">"][i])
        rv = selfc["v"][i] / max(1, tot["v"][i])
        rigid = sum(1 for d in (">", "v", "<", "^") if tot4[(i, d)] and top[(i, d)] / tot4[(i, d)] >= 0.6)
        if (rh >= self_ratio and rv >= self_ratio) or (len(nbs[i]) >= min_neighbors and rigid <= 2):
            terrain.add(i)
        # murs / clôtures : très fréquents, répétés seulement à l'horizontale -> séparateurs.
        # (un toit de maison est rare : il reste dans l'objet)
        elif e["count"] >= wall_min_count and rh >= 2 * self_ratio and rv < self_ratio:
            walls.add(i)
    return terrain, walls


def void_walls(grids, terrain, min_ratio=0.5, min_occ=2, rounds=3, prop=0.7):
    """Murs des intérieurs : tuiles collées au VIDE (hors de la pièce, -1) dans au moins min_ratio de
    leurs occurrences, puis les rangées de mur en dessous (au-dessus = mur, en dessous = sol ou mur,
    au moins prop des cas). Un meuble adossé au mur a en dessous un autre morceau de meuble : il reste."""
    occ, void = Counter(), Counter()
    up, down, n = Counter(), Counter(), Counter()
    for g in grids:
        G = g["grid"]
        H, W = G.shape
        P = np.pad(G, 1, constant_values=-2)  # -2 = bord de la zone (ne compte pas comme vide)
        core = P[1:-1, 1:-1]
        nb = [P[:-2, 1:-1], P[2:, 1:-1], P[1:-1, :-2], P[1:-1, 2:]]
        touch = np.zeros_like(core, bool)
        for q in nb:
            touch |= q == -1
        m = core >= 0
        for t, v in zip(core[m].tolist(), touch[m].tolist()):
            occ[t] += 1
            void[t] += v
    walls = {t for t, c in occ.items() if c >= min_occ and void[t] / c >= min_ratio and t not in terrain}
    for _ in range(rounds):
        up.clear(); down.clear(); n.clear()
        for g in grids:
            G = g["grid"]
            for y in range(1, G.shape[0] - 1):
                for x in range(G.shape[1]):
                    t = G[y, x]
                    if t < 0 or t in walls or t in terrain:
                        continue
                    n[t] += 1
                    up[t] += G[y - 1, x] in walls
                    down[t] += G[y + 1, x] in walls or G[y + 1, x] in terrain
        new = {t for t, c in n.items() if c >= min_occ and up[t] / c >= prop and down[t] / c >= prop}
        if not new - walls:
            break
        walls |= new
    return walls


def instances(grids, terrain, walls=(), max_tiles=144, max_side=16):
    """Composantes de tuiles non-terrain (et non-mur) voisines dans chaque zone : les occurrences."""
    stop = set(terrain) | set(walls)
    found = []
    for g in grids:
        G = g["grid"]
        H, W = G.shape
        seen = np.zeros_like(G, bool)
        for y in range(H):
            for x in range(W):
                if seen[y, x] or G[y, x] < 0 or G[y, x] in stop:
                    continue
                stack, cells = [(y, x)], []
                seen[y, x] = True
                while stack:
                    cy, cx = stack.pop()
                    cells.append((cy, cx))
                    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                        ny, nx = cy + dy, cx + dx
                        if not (0 <= ny < H and 0 <= nx < W) or seen[ny, nx]:
                            continue
                        b = G[ny, nx]
                        if b < 0 or b in stop:
                            continue
                        seen[ny, nx] = True
                        stack.append((ny, nx))
                ys = [c[0] for c in cells]; xs = [c[1] for c in cells]
                y0, x0, y1, x1 = min(ys), min(xs), max(ys) + 1, max(xs) + 1
                # terrain enfermé dans l'objet (toit plat, cour intérieure) : il en fait partie
                inside = np.zeros((y1 - y0, x1 - x0), bool)
                for cy, cx in cells:
                    inside[cy - y0, cx - x0] = True
                outside = ndimage.binary_propagation(
                    np.pad(np.zeros_like(inside), 1, constant_values=True), mask=np.pad(~inside, 1, constant_values=True))[1:-1, 1:-1]
                for yy, xx in zip(*np.nonzero(~inside & ~outside)):
                    if G[y0 + yy, x0 + xx] >= 0 and G[y0 + yy, x0 + xx] not in walls:
                        cells.append((y0 + yy, x0 + xx))
                        seen[y0 + yy, x0 + xx] = True
                layout = np.full((y1 - y0, x1 - x0), -1, np.int32)
                for cy, cx in cells:
                    layout[cy - y0, cx - x0] = G[cy, cx]
                # sols de référence : tuiles de terrain autour de l'objet, des plus fréquentes aux moins
                ring = Counter()
                cellset = set(cells)
                for cy, cx in cells:
                    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < H and 0 <= nx < W and (ny, nx) not in cellset and G[ny, nx] in terrain:
                            ring[int(G[ny, nx])] += 1
                found.append({"map": g["dir"], "region": g["region"], "sheet": g["sheet"],
                              "pos": [int(x0), int(y0)], "layout": layout,
                              "grounds": [t for t, _ in ring.most_common(4)],
                              "n": len(cells),
                              "too_big": len(cells) > max_tiles or max(y1 - y0, x1 - x0) > max_side})
    return found


_HASHES = {}


def signature(layout, hashes=None):
    """Empreinte d'une disposition, calculée sur le CONTENU des tuiles (hash de pixels de la bibliothèque),
    pas sur leurs numéros : reconstruire la bibliothèque (nouvelle feuille, grille corrigée) ne casse pas
    les corrections rangées par signature."""
    hashes = hashes if hashes is not None else _HASHES.get("cur")
    if hashes is None:
        return hashlib.blake2b(layout.tobytes() + bytes(layout.shape), digest_size=6).hexdigest()
    key = "|".join(",".join(hashes[i] if i >= 0 else "-" for i in row) for row in layout.tolist())
    return hashlib.blake2b(key.encode(), digest_size=6).hexdigest()


def _shadow(tile, ground, keep):
    """Pixels d'ombre : sol assombri du même facteur sur R, G, B. Renvoie (masque, alpha)."""
    g = ground[..., :3].astype(np.float32)
    p = tile[..., :3].astype(np.float32)
    ok = (g >= 24).all(-1) & keep
    k = np.where(g > 0, p / np.maximum(g, 1), 1)
    km = k.mean(-1)
    cand = ok & (km >= SHADOW_K[0]) & (km <= SHADOW_K[1]) & (k.max(-1) - k.min(-1) <= SHADOW_SPREAD)
    return cand, np.clip(np.round(255 * (1 - km)), 0, 255).astype(np.uint8)


def _edge_piece(layout, pixels, terrain, cover=0.9):
    """Tuiles de transition entre deux sols (bord de falaise, rive, chemin) : chaque tuile est faite, à
    cover près, de pixels de DEUX tuiles de terrain (aux mêmes positions)."""
    ter = [pixels(int(g)) for g in terrain]
    if not ter:
        return False
    for i in layout[layout >= 0].ravel().tolist():
        tile = pixels(int(i))[..., :3]
        eq = np.stack([(tile == g[..., :3]).all(-1) for g in ter])  # (n_terrain, t, t)
        score = eq.reshape(len(ter), -1).sum(1)
        top = np.argsort(score)[-6:]
        best = 0.0
        for a in top:
            for b in top:
                best = max(best, (eq[a] | eq[b]).mean())
        if best < cover:
            return False
    return True


def render(layout, grounds, pixels, t, subtract=True, shadows=True, min_blob=6):
    """Image de l'objet. Pour chaque tuile, le sol retiré est celui (parmi les sols voisins) qui en
    explique le plus de pixels. Seules les plages de sol d'au moins min_blob pixels ET reliées au bord
    de l'objet (ou à une case vide) sont retirées : pas de confettis dans une texture qui ressemble au sol.
    L'ombre devient du noir semi-transparent (si elle touche le vide). Renvoie (image RGBA, pixels d'ombre)."""
    h, w = layout.shape
    out = np.zeros((h * t, w * t, 4), np.uint8)
    gpx = [pixels(g) for g in grounds] if subtract else []
    same = np.zeros((h * t, w * t), bool)
    ground = np.zeros((h * t, w * t, 4), np.uint8)
    for y in range(h):
        for x in range(w):
            i = layout[y, x]
            if i < 0:
                continue
            tile = pixels(int(i))
            sl = (slice(y * t, (y + 1) * t), slice(x * t, (x + 1) * t))
            out[sl] = tile
            if gpx:
                best = max(gpx, key=lambda g: int((tile[..., :3] == g[..., :3]).all(-1).sum()))
                same[sl] = (tile[..., :3] == best[..., :3]).all(-1) & (tile[..., 3] > 0)
                ground[sl] = best
    if not same.any():
        return out, 0
    outside = out[..., 3] == 0
    border = np.zeros_like(same)
    border[0, :] = border[-1, :] = True
    border[:, 0] = border[:, -1] = True
    lab, n = ndimage.label(same)
    sizes = ndimage.sum(np.ones_like(same), lab, index=np.arange(1, n + 1))
    touch = set(np.unique(lab[(border | ndimage.binary_dilation(outside)) & same]).tolist()) - {0}
    ok = [k for k in range(1, n + 1) if sizes[k - 1] >= min_blob and k in touch]
    rm = np.isin(lab, ok)
    out[rm] = 0
    n_sh = 0
    if shadows:
        m, a = _shadow(out, ground, (out[..., 3] > 0) & ~same)
        if m.any():
            # seulement l'ombre d'un seul tenant avec le sol retiré (pas un pixel sombre au milieu de l'objet)
            lab2, _ = ndimage.label(m)
            touch2 = ndimage.binary_dilation(out[..., 3] == 0) & m
            keep = np.isin(lab2, np.unique(lab2[touch2])) & m if touch2.any() else np.zeros_like(m)
            out[keep, :3] = 0
            out[keep, 3] = a[keep]
            n_sh = int(keep.sum())
    return out, n_sh


def overrides_path(game):
    return os.path.join(config.PIPELINE, "objects", f"{game}.json")


def load_overrides(game):
    """Corrections de tout le jeu : ancien fichier rpg/pipeline/objects/<jeu>.json + fiches des pages."""
    ov = {"drop": [], "names": {}, "split": {}}
    p = overrides_path(game)
    if os.path.exists(p):
        with open(p) as f:
            old = json.load(f)
        ov["drop"] += old.get("drop", [])
        ov["names"].update(old.get("names", {}))
    for c in pages(game):
        o = c.get("overrides", {})
        ov["drop"] += o.get("drop", [])
        ov["names"].update(o.get("names", {}))
        ov["split"].update(o.get("split", {}))
    return ov


def save_overrides(game, ov):
    os.makedirs(os.path.dirname(overrides_path(game)), exist_ok=True)
    with open(overrides_path(game), "w") as f:
        json.dump(ov, f, indent=1)


def page_id(game, n):
    return f"obj_{game}_{n:02d}"


def pages(game):
    d = os.path.join(config.SHEETS, game)
    out = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f.startswith("obj_") and f.endswith(".json"):
            out.append(config._read_json(os.path.join(d, f)))
    return out


def _split_layout(layout, rects):
    """Découpe une disposition en morceaux : un par rectangle (x, y, l, h en tuiles), puis une pièce par
    groupe connexe de tuiles restantes."""
    left = layout >= 0
    parts = []
    for x, y, w, h in rects:
        sub = np.full_like(layout, -1)
        sub[y:y + h, x:x + w] = layout[y:y + h, x:x + w]
        left[y:y + h, x:x + w] = False
        parts.append(sub)
    lab, n = ndimage.label(left)
    for k in range(1, n + 1):
        parts.append(np.where(lab == k, layout, -1))
    out = []
    for sub in parts:
        ys, xs = np.nonzero(sub >= 0)
        if len(ys):
            out.append((sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1], (int(xs.min()), int(ys.min()))))
    return out


def build(game, **kw):
    """Reconstruction sous verrou (plusieurs agents relisent des pages du même jeu en parallèle)."""
    with config.lock(f"objects_{game}"):
        return _build(game, **kw)


_GROUNDS = {"expand": lambda g: g}


def _ground_expander(terrain, pixels, max_dist=24.0, extra=10):
    """Sols candidats d'un objet : ses sols voisins + les tuiles de terrain de couleur moyenne proche (eau à
    vagues décalées, herbe à motifs : la tuile SOUS l'objet n'est pas toujours celle d'à côté)."""
    ids = sorted(int(i) for i in terrain)
    if not ids:
        return lambda g: g
    M = np.array([pixels(i)[..., :3].reshape(-1, 3).mean(0) for i in ids])
    pos = {i: k for k, i in enumerate(ids)}

    def expand(grounds):
        out = list(grounds)
        for g in grounds[:2]:
            if g not in pos:
                continue
            d = np.linalg.norm(M - M[pos[g]], axis=1)
            for k in np.argsort(d)[:extra + 1]:
                if d[k] <= max_dist and ids[k] not in out:
                    out.append(ids[k])
        return out
    return expand


def _pixel_parts(img, layout, t):
    """Groupes de tuiles dont les pixels (sol retiré, ombre comprise) se touchent : deux meubles voisins
    sur la grille mais séparés par du sol sont deux objets. Les tuiles vides (sol seul) sont écartées.
    Renvoie une liste de masques (h, w) de cases."""
    h, w = layout.shape
    lab, n = ndimage.label(img[..., 3] > 0, structure=np.ones((3, 3)))
    parent = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    owner = {}
    cells = []
    for y in range(h):
        for x in range(w):
            if layout[y, x] < 0:
                continue
            ls = set(np.unique(lab[y * t:(y + 1) * t, x * t:(x + 1) * t]).tolist()) - {0}
            if not ls:
                continue
            parent[(y, x)] = (y, x)
            cells.append((y, x))
            for l in ls:
                if l in owner:
                    parent[find((y, x))] = find(owner[l])
                else:
                    owner[l] = (y, x)
    comps = defaultdict(list)
    for c in cells:
        comps[find(c)].append(c)
    out = []
    for cs in comps.values():
        m = np.zeros((h, w), bool)
        for y, x in cs:
            m[y, x] = True
        out.append(m)
    return out


def _auto_split(groups, ov, pixels, t):
    """Découpe automatique de chaque objet en groupes de pixels connexes (voir _pixel_parts). Les morceaux
    de même disposition, d'où qu'ils viennent, sont fusionnés. Exceptions : objets découpés à la main."""
    out = defaultdict(list)
    for sig, os_ in groups.items():
        o = os_[0]
        if sig in ov.get("nosplit", []) or o["too_big"]:
            out[sig] += os_
            continue
        gr = Counter(int(g) for x in os_ for g in x["grounds"])
        img, _ = render(o["layout"], _GROUNDS["expand"]([g for g, _ in gr.most_common(4)]), pixels, t)
        parts = _pixel_parts(img, o["layout"], t)
        nonempty = int((o["layout"] >= 0).sum())
        if len(parts) <= 1 and (not parts or int(parts[0].sum()) == nonempty):
            out[sig] += os_
            continue
        for m in parts:
            ys, xs = np.nonzero(m)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            sub = np.where(m, o["layout"], -1)[y0:y1, x0:x1]
            ssig = signature(sub)
            for x in os_:
                out[ssig].append(dict(x, layout=sub, pos=[x["pos"][0] + int(x0), x["pos"][1] + int(y0)],
                                      n=int((sub >= 0).sum()), parent=x.get("parent") or sig, auto_parent=sig,
                                      too_big=False))
    return out


def _build(game, min_tiles=1, shadows=True):
    """Extrait les objets d'un jeu vers rpg/assets/<jeu>/objects/ et met à jour les pages de vérification.
    Les objets sont identifiés par la signature de leur disposition de tuiles (stable tant que la
    bibliothèque ne change pas). Renvoie des statistiques."""
    ov = load_overrides(game)
    lib, pixels = load_library(game)
    _HASHES["cur"] = [e["hash"] for e in lib["tiles"]]
    t = lib["tile"]
    grids = load_grids(game)
    pair = neighbor_stats(grids)
    terrain, walls = classify_terrain(lib, pair)
    walls |= void_walls(grids, terrain)
    _GROUNDS["expand"] = _ground_expander(terrain, pixels)
    occ = instances(grids, terrain, walls)
    groups = defaultdict(list)
    parents = {}
    for o in occ:
        sig = signature(o["layout"])
        if sig in ov["split"]:
            parents.setdefault(sig, o)
            for sub, (dx, dy) in _split_layout(o["layout"], ov["split"][sig]):
                o2 = dict(o, layout=sub, pos=[o["pos"][0] + dx, o["pos"][1] + dy], n=int((sub >= 0).sum()),
                          parent=sig, too_big=int((sub >= 0).sum()) > 144 or max(sub.shape) > 16)
                groups[signature(sub)].append(o2)
        else:
            groups[sig].append(o)
    groups = _auto_split(groups, ov, pixels, t)
    out = os.path.join(config.ASSETS, game, "objects")
    os.makedirs(out, exist_ok=True)
    catalog, wanted = [], set()
    for sig, o in parents.items():  # gardés sur leur page (annulable : objsplit ID N undo), pas d'image
        catalog.append({"sig": sig, "name": "(découpé)", "kind": "object", "dropped": True, "split": True,
                        "size": [int(o["layout"].shape[1]), int(o["layout"].shape[0])], "count": 0,
                        "occurrences": [{"map": o["map"], "region": o["region"], "sheet": o["sheet"], "pos": o["pos"]}]})
    for sig, os_ in sorted(groups.items(), key=lambda kv: (-len(kv[1]), -kv[1][0]["n"], kv[0])):
        o = os_[0]
        if o["n"] < min_tiles or sig in ov["split"]:
            continue
        kind = "structure" if o["too_big"] else "object"
        gr = Counter(int(g) for x in os_ for g in x["grounds"])
        grounds = _GROUNDS["expand"]([g for g, _ in gr.most_common(4)])
        dropped = sig in ov["drop"]
        name = config.slug(ov["names"][sig]) if sig in ov["names"] else f"{kind}_{sig}"
        entry = {"sig": sig, "name": name, "kind": kind, "dropped": dropped,
                 "size": [int(o["layout"].shape[1]), int(o["layout"].shape[0])],
                 "tiles": o["layout"].tolist(), "grounds": grounds, "count": len(os_),
                 "parent": o.get("parent"),
                 "occurrences": [{"map": x["map"], "region": x["region"], "sheet": x["sheet"], "pos": x["pos"]} for x in os_[:20]]}
        if not dropped:
            img, n_sh = render(o["layout"], grounds, pixels, t, shadows=shadows)
            entry["shadow_px"] = n_sh
            # 1-2 tuiles entièrement opaques après retrait du sol : morceau de terrain (bord de chemin,
            # variante d'herbe), pas un objet -> catalogue à part, hors pages de vérification
            if o["n"] <= 2 and ((img[..., 3] == 255).mean() > 0.97 or _edge_piece(o["layout"], pixels, terrain)):
                entry["kind"] = kind = "terrain_piece"
            elif (img[..., 3] > 0).mean() < 0.06:
                entry["kind"] = kind = "terrain_piece"  # presque vide une fois le sol retiré
            fn = os.path.join(out, f"{name}.png")
            Image.fromarray(img).save(fn + ".tmp.png")
            os.replace(fn + ".tmp.png", fn)
            wanted.add(f"{name}.png")
        catalog.append(entry)
    for f in os.listdir(out):
        if f.endswith(".png") and f not in wanted:
            os.remove(os.path.join(out, f))
    config.write_json_atomic(os.path.join(out, "objects.json"),
                             {"game": game, "tile": t, "terrain": sorted(int(x) for x in terrain), "walls": sorted(int(w) for w in walls),
                              "objects": [c for c in catalog if c["kind"] != "terrain_piece"],
                              "terrain_pieces": [c for c in catalog if c["kind"] == "terrain_piece"]})
    n_pages = assign_pages(game, [c for c in catalog if c["kind"] != "terrain_piece"])
    return {"terrain": len(terrain), "murs": len(walls), "occurrences": len(occ),
            "objets": sum(1 for c in catalog if c["kind"] == "object" and not c["dropped"]),
            "structures": sum(1 for c in catalog if c["kind"] == "structure" and not c["dropped"]),
            "morceaux_terrain": sum(1 for c in catalog if c["kind"] == "terrain_piece"),
            "jetés": sum(1 for c in catalog if c["dropped"]), "pages": n_pages}


def _new_page(game, n):
    return {"id": page_id(game, n), "game": game, "section": "objects", "title": f"Objets {game} page {n:02d}",
            "src": None, "category": "objects", "type": "objects", "status": "todo", "params": {},
            "overrides": {"drop": [], "names": {}, "split": {}}, "regions": {"sigs": []}, "notes": ""}


def assign_pages(game, catalog):
    """Répartit les objets en pages STABLES : un objet garde sa page ; les morceaux d'un objet découpé
    vont sur la page du parent ; les nouveaux remplissent la dernière page puis de nouvelles.
    Le contenu d'une page (liste de signatures) fait partie de son empreinte d'état : si elle change,
    la confirmation de la page devient caduque."""
    by_id = {c["id"]: c for c in pages(game)}
    where = {}
    for pid, c in by_id.items():
        for s in c["regions"]["sigs"]:
            where[s] = pid
    for pid, c in by_id.items():
        for s in c["overrides"].get("split", {}):
            where.setdefault(s, pid)
    present = {c["sig"] for c in catalog}
    new = defaultdict(list)
    orphans = []
    for c in catalog:
        pid = where.get(c["sig"]) or where.get(c.get("parent"))
        if pid:
            new[pid].append(c["sig"])
        else:
            orphans.append(c["sig"])
    n = len(by_id)
    for s in orphans:
        last = page_id(game, n - 1) if n else None
        if last is None or len(new[last]) >= PAGE:
            last = page_id(game, n)
            by_id[last] = _new_page(game, n)
            n += 1
        new[last].append(s)
    for pid, c in by_id.items():
        # ordre STABLE : les objets déjà sur la page gardent leur numéro, les nouveaux s'ajoutent à la fin
        got = set(new.get(pid, []))
        sigs = [x for x in c["regions"]["sigs"] if x in got]
        sigs += [x for x in new.get(pid, []) if x not in set(sigs)]
        if c["regions"]["sigs"] != sigs or not os.path.exists(config.sheet_path(game, pid)):
            if os.path.exists(config.sheet_path(game, pid)):
                c = config.load(pid)  # relue : un agent a pu la corriger entre-temps
            c["regions"] = {"sigs": sigs}
            config.save(c)
    return len(by_id)


def page_objects(cfg):
    """Objets d'une page (dans l'ordre de la page), y compris les jetés : [(n, entrée), ...]."""
    with open(os.path.join(config.ASSETS, cfg["game"], "objects", "objects.json")) as f:
        cat = {c["sig"]: c for c in json.load(f)["objects"]}
    drops = set(cfg["overrides"].get("drop", []))
    out = []
    for n, s in enumerate(cfg["regions"]["sigs"], 1):
        e = dict(cat.get(s) or {"sig": s, "dropped": True, "name": "(disparu)", "size": [0, 0], "count": 0,
                                "kind": "object", "occurrences": []})
        if s in drops:
            e["dropped"] = True
        out.append((n, e))
    return out


PER_IMAGE = 10  # objets par planche : une image lisible pour un modèle de vision (pas de réduction)


def montage_page(cfg, scale=None, width=1000):
    """Planches d'une page, PER_IMAGE objets par image : chaque objet numéroté, sur damier, grille de
    tuiles en pointillés ; à côté, le même endroit dans la carte d'origine. Objets jetés barrés en rouge."""
    from PIL import ImageDraw
    from .qa import _checker, _font
    game = cfg["game"]
    base = os.path.join(config.ASSETS, game, "objects")
    with open(os.path.join(base, "objects.json")) as f:
        t = json.load(f)["tile"]
    font = _font(14)
    out = os.path.join(config.QA_DIR, cfg["id"])
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.startswith("objets_") and f.endswith(".png"):
            os.remove(os.path.join(out, f))
    items = page_objects(cfg)
    paths = []
    for k in range(0, len(items), PER_IMAGE):
        cells = []
        for n, c in items[k:k + PER_IMAGE]:
            im = None
            fn = os.path.join(base, c["name"] + ".png")
            if not c.get("dropped") and os.path.exists(fn):
                im = Image.open(fn).convert("RGBA")
            w, h = (c["size"][0] * t, c["size"][1] * t)
            sc = scale or (4 if max(w, h) <= 32 else 3 if max(w, h) <= 64 else 2 if max(w, h) <= 160 else 1)
            while (2 * w + 2 * t) * sc > width - 16 and sc > 1:
                sc -= 1
            ctx = None
            if c.get("occurrences"):
                o = c["occurrences"][0]
                p = os.path.join(config.ASSETS, game, "maps", o["map"], f"region_{o['region']}.png")
                if os.path.exists(p):
                    x0, y0 = o["pos"][0] * t, o["pos"][1] * t
                    ctx = Image.open(p).convert("RGBA").crop((x0 - t, y0 - t, x0 + w + t, y0 + h + t))
            cells.append((n, c, im, ctx, w, h, sc))
        x = y = row_h = 0
        placed = []
        for n, c, im, ctx, w, h, sc in cells:
            cw = max(w * sc + ((w + 2 * t) * sc + 10 if ctx else 0) + 24, 140)
            ch = max(h * sc, (h + 2 * t) * sc if ctx else 0) + 22
            if x + cw > width and x > 0:
                x, y, row_h = 0, y + row_h, 0
            placed.append((n, c, im, ctx, w, h, sc, x, y))
            x += cw
            row_h = max(row_h, ch)
        sheet = Image.new("RGBA", (width, max(y + row_h + 4, 20)), (50, 50, 60, 255))
        d = ImageDraw.Draw(sheet)
        for n, c, im, ctx, w, h, sc, x, y in placed:
            d.text((x, y), f"#{n}  {c['size'][0]}x{c['size'][1]}", fill=(255, 90, 90) if c.get("dropped") else (255, 255, 120), font=font)
            oy = y + 18
            if w and h:
                sheet.alpha_composite(_checker(w * sc, h * sc, 4), (x, oy))
            if im is not None:
                sheet.alpha_composite(im.resize((w * sc, h * sc), Image.NEAREST), (x, oy))
                for gx in range(0, w + 1, t):
                    for yy in range(oy, oy + h * sc, 4):
                        sheet.putpixel((min(x + gx * sc, width - 1), min(yy, sheet.height - 1)), (0, 200, 255, 255))
                for gy in range(0, h + 1, t):
                    for xx in range(x, min(x + w * sc, width), 4):
                        sheet.putpixel((xx, min(oy + gy * sc, sheet.height - 1)), (0, 200, 255, 255))
            if c.get("dropped") and w and h:
                d.line((x, oy, x + w * sc, oy + h * sc), fill=(255, 60, 60), width=3)
                d.line((x + w * sc, oy, x, oy + h * sc), fill=(255, 60, 60), width=3)
            if ctx is not None:
                sheet.alpha_composite(ctx.resize((ctx.width * sc, ctx.height * sc), Image.NEAREST), (x + w * sc + 10, oy))
        pth = os.path.join(out, f"objets_{k // PER_IMAGE}.png")
        sheet.save(pth)
        paths.append(pth)
    return paths


def page_report(cfg):
    lines = [f"{cfg['id']} : {len(cfg['regions']['sigs'])} objet(s) — statut {cfg['status']}"]
    for n, c in page_objects(cfg):
        occ = c.get("occurrences") or [{}]
        flag = "DÉCOUPÉ (morceaux plus bas) " if c.get("split") else "JETÉ " if c.get("dropped") else ""
        extra = f" ombre {c['shadow_px']}px" if c.get("shadow_px") else ""
        lines.append(f"  #{n:<3} {flag}{c['name']:<28} {c['size'][0]}x{c['size'][1]} tuiles  x{c['count']:<3} "
                     f"{c['kind']}{extra}  ex. {occ[0].get('map', '?')}")
    return "\n".join(lines)


def montage(game, start=0, count=120, scale=2):
    """Planche numérotée des objets (ordre du catalogue : les plus fréquents d'abord)."""
    from PIL import ImageDraw
    from .qa import _checker, _font, MAX_PAGE
    base = os.path.join(config.ASSETS, game, "objects")
    with open(os.path.join(base, "objects.json")) as f:
        cat = json.load(f)["objects"]
    font = _font(10)
    sel = cat[start:start + count]
    tiles_ = [(i + start, c, Image.open(os.path.join(base, c["name"] + ".png")).convert("RGBA")) for i, c in enumerate(sel)]
    x = y = row_h = 0
    placed = []
    for i, c, im in tiles_:
        w, h = im.width * scale, im.height * scale
        if x + w + 8 > MAX_PAGE:
            x, y, row_h = 0, y + row_h, 0
        placed.append((i, c, im, x, y))
        x += max(w, 40) + 8
        row_h = max(row_h, h + 14)
    W = MAX_PAGE
    H = y + row_h + 4
    sheet = Image.new("RGBA", (W, H), (50, 50, 60, 255))
    d = ImageDraw.Draw(sheet)
    for i, c, im, x, y in placed:
        w, h = im.width * scale, im.height * scale
        sheet.alpha_composite(_checker(w, h, 4), (x, y + 12))
        sheet.alpha_composite(im.resize((w, h), Image.NEAREST), (x, y + 12))
        d.text((x, y), f"#{i} x{c['count']}", fill=(255, 255, 120) if c["kind"] == "object" else (255, 120, 120), font=font)
    out = os.path.join(config.QA_DIR, f"objects_{game}")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"objects_{start:05d}.png")
    sheet.save(path)
    return path
