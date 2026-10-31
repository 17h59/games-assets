"""Extraction des feuilles de type sprites / characters / effects / items.

Étapes, pour chaque partie de la feuille (zones manuelles avec leurs propres réglages, puis le reste) :
fond -> composantes -> filtres (miettes, texte, encarts, déchets) -> grille -> corrections manuelles
(ancrées sur des points de la feuille) -> ordre de lecture -> regroupement en entités -> écriture.
"""
import json
import os
import shutil

from collections import Counter

import numpy as np
from PIL import Image

from . import config, grid, imageops, templates


# ---------------------------------------------------------------- corrections manuelles

def _at(items, x, y, kinds=None):
    """Item dont la boîte contient (x, y) ; le plus petit si plusieurs."""
    hits = [it for it in items if it["x"] <= x < it["x"] + it["w"] and it["y"] <= y < it["y"] + it["h"]
            and (kinds is None or it["kind"] in kinds)]
    return min(hits, key=lambda it: it["w"] * it["h"]) if hits else None


def _union(group):
    x0 = min(it["x"] for it in group)
    y0 = min(it["y"] for it in group)
    x1 = max(it["x"] + it["w"] for it in group)
    y1 = max(it["y"] + it["h"] for it in group)
    labels = sorted({lb for it in group for lb in it["labels"]})
    # pixels assemblés tout de suite : les membres peuvent venir de zones différentes (labels différents)
    px = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
    for it in group:
        sub = _pixels(it.get("_a"), it)
        m = sub[..., 3] > 0
        px[it["y"] - y0:it["y"] - y0 + it["h"], it["x"] - x0:it["x"] - x0 + it["w"]][m] = sub[m]
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "labels": labels,
            "area": sum(it["area"] for it in group), "ncolors": max(it["ncolors"] for it in group),
            "dominant": group[0]["dominant"], "dom_frac": group[0].get("dom_frac", 0), "kind": "sprite",
            "_labs": group[0]["_labs"], "_a": group[0].get("_a"), "_px": px, "zone": group[0].get("zone")}


def apply_split(items, points, lab_fine, labs, done, own_only=False):
    """split (par zone : il faut les composantes sans fusion de la zone). `done` reçoit les points traités.
    own_only (param split_own) : seulement les morceaux faits des pixels de l'item visé ; sinon (historique)
    toutes les composantes présentes dans sa BOÎTE, ce qui duplique les sprites entourés par un grand cadre."""
    log = []
    for x, y in points:
        it = _at(items, x, y)
        if not it:
            continue
        done.add((x, y))
        sub = lab_fine[it["y"]:it["y"] + it["h"], it["x"]:it["x"] + it["w"]]
        own = _pixels(None, it)[..., 3] > 0 if own_only else np.ones(sub.shape, bool)
        inner = [lb for lb in np.unique(sub[own]) if lb]
        if len(inner) < 2:
            log.append(f"split ({x},{y}) : un seul morceau, rien à séparer"); continue
        items.remove(it)
        for lb in inner:
            if own_only:
                ys, xs = np.nonzero((sub == lb) & own)
                xs, ys = xs + it["x"], ys + it["y"]
            else:
                ys, xs = np.nonzero(lab_fine == lb)
            items.append({"x": int(xs.min()), "y": int(ys.min()), "w": int(xs.max() - xs.min() + 1),
                          "h": int(ys.max() - ys.min() + 1), "labels": [("f", int(lb))], "area": int(len(xs)),
                          "ncolors": it["ncolors"], "dominant": it["dominant"], "dom_frac": 0, "kind": "sprite",
                          "_labs": labs, "_a": it.get("_a"), "zone": it.get("zone")})
    return log


def apply_global(items, ov):
    """Corrections appliquées sur la feuille ENTIÈRE (toutes zones confondues) : un élément peut
    chevaucher une zone, deux morceaux à fusionner peuvent être dans deux zones différentes."""
    log = []
    # add : une boîte forcée regroupe tout ce dont le centre tombe dedans
    for bx, by, bw, bh in ov.get("add", []):
        inside = [it for it in items if bx <= it["x"] + it["w"] / 2 < bx + bw and by <= it["y"] + it["h"] / 2 < by + bh]
        if not inside:
            log.append(f"add {bx},{by},{bw},{bh} : vide"); continue
        for it in inside:
            items.remove(it)
        items.append(_union(inside))
    # merge : chaque groupe de points -> un seul item
    for pts in ov.get("merge", []):
        group = []
        for x, y in pts:
            it = _at(items, x, y)
            if it and it not in group:
                group.append(it)
        if len(group) < 2:
            log.append(f"merge {pts} : moins de 2 items trouvés"); continue
        for it in group:
            items.remove(it)
        items.append(_union(group))
    for x, y in ov.get("drop", []):
        it = _at(items, x, y)
        if it:
            it["kind"] = "dropped"
        else:
            log.append(f"drop ({x},{y}) : aucun item")
    for x, y in ov.get("keep", []):
        it = _at(items, x, y)
        if it:
            it["kind"] = "sprite"
        else:
            log.append(f"keep ({x},{y}) : aucun item")
    for x, y in ov.get("cut", []):
        it = _at(items, x, y)
        if it:
            it["cut"] = True
        else:
            log.append(f"cut ({x},{y}) : aucun item")
    for entry in ov.get("names", []):
        it = _at(items, *entry["point"])
        if it:
            it["name"] = config.slug(entry["name"])
    return log


# ---------------------------------------------------------------- ordre et regroupement

def reading_order(items, row_tol):
    """Lignes : rangées de grille quand les items en viennent, sinon d'après le bas des sprites
    (les pieds) ; puis gauche -> droite."""
    gridrows = {}
    for it in items:
        if "block" in it:
            gridrows.setdefault((it["block"], it["row"]), []).append(it)
    rows = [{"bottom": max(i["y"] + i["h"] for i in v), "items": v, "grid": True} for v in gridrows.values()]
    loose = []
    for it in sorted((i for i in items if "block" not in i), key=lambda it: it["y"] + it["h"]):
        b = it["y"] + it["h"]
        if loose and abs(b - loose[-1]["bottom"]) <= row_tol:
            loose[-1]["items"].append(it)
        else:
            loose.append({"bottom": b, "items": [it]})
    rows += loose
    for r in rows:
        r["items"].sort(key=lambda it: it["x"])
    rows.sort(key=lambda r: (min(i["y"] for i in r["items"]), min(i["x"] for i in r["items"])))
    return rows


def segments(row_items, split_gap):
    """Coupe une ligne là où il y a un trou : case vide (grille) ou écart > split_gap px (taches)."""
    segs, cur = [], []
    for it in row_items:
        if cur and "col" in it and "col" in cur[-1]:
            brk = it["col"] - cur[-1]["col"] > 1
        else:
            brk = cur and it["x"] - (cur[-1]["x"] + cur[-1]["w"]) > split_gap
        if cur and it.get("set") != cur[-1].get("set"):
            brk = True  # une animation ne chevauche jamais deux ensembles (légendes)
        if cur and brk:
            segs.append(cur); cur = []
        cur.append(it)
    if cur:
        segs.append(cur)
    return segs


def _partition(seg, sizes, gaps=None):
    """Découpe un segment en morceaux de tailles autorisées : le moins de morceaux possible,
    puis à égalité en coupant là où l'écart entre deux sprites voisins est le plus grand.
    None si impossible."""
    n = len(seg)
    if gaps is None:
        gaps = [seg[i + 1]["x"] - (seg[i]["x"] + seg[i]["w"]) for i in range(n - 1)]
    best = {0: ((0, 0.0), [])}  # position -> ((-morceaux, somme des écarts aux coupes), coupes)
    for pos in range(n):
        if pos not in best:
            continue
        sc, cuts = best[pos]
        for k in sizes:
            nxt = pos + k
            if nxt > n:
                continue
            add = gaps[nxt - 1] if nxt < n else 0
            cand = ((sc[0] - 1, sc[1] + add), cuts + [nxt])
            if nxt not in best or cand[0] > best[nxt][0]:
                best[nxt] = cand
    if n not in best:
        return None
    out, prev = [], 0
    for c in best[n][1]:
        out.append(seg[prev:c]); prev = c
    return out


def group_entities(rows, p):
    ents, warnings = [], []
    sizes = sorted({p["frames"], *p["frames_alt"]}, reverse=True)
    for r in rows:
        for seg in segments(r["items"], p["row_split_gap"]):
            # coupes manuelles : un item marqué "cut" commence une nouvelle entité
            parts, cur = [], []
            for it in seg:
                if it.get("cut") and cur:
                    parts.append(cur); cur = []
                cur.append(it)
            parts.append(cur)
            for part in parts:
                if p["group"] == "rows":
                    ents.append(part); continue
                split = _partition(part, sizes)
                if split is None:
                    n = p["frames"]
                    warnings.append({"flag": "row_count", "x": part[0]["x"], "y": part[0]["y"],
                                     "msg": f"segment de {len(part)} sprites : pas décomposable en {sizes}"})
                    split = [part[i:i + n] for i in range(0, len(part), n)]
                ents.extend(split)
    return ents, warnings


def _columns(items, tol_frac):
    """Colonnes : regroupement 1D des centres horizontaux (tolérance = tol_frac x largeur médiane)."""
    if not items:
        return []
    mw = float(np.median([it["w"] for it in items]))
    srt = sorted(items, key=lambda it: it["x"] + it["w"] / 2)
    cols, cur = [], [srt[0]]
    for it in srt[1:]:
        c = it["x"] + it["w"] / 2
        mean = sum(i["x"] + i["w"] / 2 for i in cur) / len(cur)
        if c - mean > tol_frac * mw:
            cols.append(cur); cur = [it]
        else:
            cur.append(it)
    cols.append(cur)
    return cols


def group_columns(kept, p):
    """Persos rangés en colonnes : une colonne = les frames d'un perso, de haut en bas."""
    ents, warnings = [], []
    sizes = sorted({p["frames"], *p["frames_alt"]}, reverse=True)
    for col in _columns(kept, p["col_tol"]):
        col.sort(key=lambda it: it["y"])
        segs, cur = [], []
        for it in col:
            if cur and it["y"] - (cur[-1]["y"] + cur[-1]["h"]) > p["row_split_gap"]:
                segs.append(cur); cur = []
            cur.append(it)
        if cur:
            segs.append(cur)
        for seg in segs:
            if p["group"] == "columns_all":
                ents.append(seg); continue
            gaps = [seg[i + 1]["y"] - (seg[i]["y"] + seg[i]["h"]) for i in range(len(seg) - 1)]
            split = _partition(seg, sizes, gaps)
            if split is None:
                warnings.append({"flag": "row_count", "x": seg[0]["x"], "y": seg[0]["y"],
                                 "msg": f"colonne de {len(seg)} sprites : pas décomposable en {sizes}"})
                split = [seg[i:i + p["frames"]] for i in range(0, len(seg), p["frames"])]
            ents.extend(split)
    ents.sort(key=lambda e: (e[0]["y"], e[0]["x"]))
    return ents, warnings


def group_blocks(rows, kept, p):
    """Persos rangés en blocs 2D (ex. 3x3) : rangée et colonne de chaque sprite, puis découpage en
    blocs de entity_shape cases. Ordre des frames : ligne par ligne (row) ou colonne par colonne (col)."""
    cw, rh = map(int, str(p["entity_shape"]).lower().split("x"))
    row_of = {id(it): ri for ri, r in enumerate(rows) for it in r["items"]}
    col_of = {id(it): ci for ci, c in enumerate(_columns(kept, p["col_tol"])) for it in c}
    groups = {}
    for it in kept:
        ri, ci = row_of[id(it)], col_of[id(it)]
        groups.setdefault((ri // rh, ci // cw), []).append((ri, ci, it))
    ents, warnings = [], []
    for key in sorted(groups):
        g = groups[key]
        g.sort(key=(lambda t: (t[0], t[1])) if p["frame_order"] == "row" else (lambda t: (t[1], t[0])))
        frames = [t[2] for t in g]
        if len(frames) != cw * rh:
            warnings.append({"flag": "row_count", "x": frames[0]["x"], "y": frames[0]["y"],
                             "msg": f"bloc {key} : {len(frames)} sprites au lieu de {cw * rh} ({p['entity_shape']})"})
        ents.append(frames)
    return ents, warnings


def _palette(a, it):
    px = _pixels(a, it)
    m = px[..., 3] > 0
    return {tuple(c) for c in px[m][:, :3].tolist()}


def _jaccard(p1, p2):
    return len(p1 & p2) / max(1, len(p1 | p2))


def _box_gap(a, b):
    dx = max(b["x"] - (a["x"] + a["w"]), a["x"] - (b["x"] + b["w"]), 0)
    dy = max(b["y"] - (a["y"] + a["h"]), a["y"] - (b["y"] + b["h"]), 0)
    return max(dx, dy)


def group_by_palette(a, kept_ordered, p):
    """Feuilles en vrac (Zelda...) : les frames d'un même personnage partagent sa palette.
    Union des sprites proches (<= palette_dist px) dont les palettes se ressemblent (>= palette_sim)."""
    pals = [_palette(a, it) for it in kept_ordered]
    parent = list(range(len(kept_ordered)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, a_ in enumerate(kept_ordered):
        for j in range(i + 1, len(kept_ordered)):
            b_ = kept_ordered[j]
            if _box_gap(a_, b_) <= p["palette_dist"] and _jaccard(pals[i], pals[j]) >= p["palette_sim"]:
                parent[find(i)] = find(j)
    groups = {}
    for i, it in enumerate(kept_ordered):
        groups.setdefault(find(i), []).append(it)
    return sorted(groups.values(), key=lambda g: (g[0]["y"], g[0]["x"]))


def caption_sets(items, cfg):
    """Ensembles par légende (sets=captions) : chaque ligne de texte de la feuille (légende du ripper :
    « Ember », « Fire Blast »...) ouvre un ensemble ; chaque sprite rejoint la légende la plus proche
    au-dessus de lui et à sa gauche. Renvoie la liste des ensembles [{id, box, point, name}]."""
    # glyphes : texte détecté, ou élément jeté (souvent à la main) qui a la hauteur d'une ligne de texte
    max_h = config.params(cfg)["text_max_h"]
    glyphs = [it for it in items if it["kind"] == "text" or (it["kind"] == "dropped" and it["h"] <= max_h)]
    glyphs.sort(key=lambda t: (t["y"] + t["h"], t["x"]))
    lines = []
    for g in sorted(glyphs, key=lambda t: t["x"]):
        b = g["y"] + g["h"]
        for ln in lines:
            if abs(ln["bottom"] - b) <= 3 and g["x"] - ln["x1"] <= 10:
                ln["x1"] = max(ln["x1"], g["x"] + g["w"]); ln["y0"] = min(ln["y0"], g["y"]); ln["n"] += 1
                break
        else:
            lines.append({"x0": g["x"], "x1": g["x"] + g["w"], "y0": g["y"], "bottom": b, "n": 1})
    lines = [ln for ln in lines if ln["n"] >= 2 or ln["x1"] - ln["x0"] >= 12]
    lines.sort(key=lambda ln: (ln["y0"], ln["x0"]))
    names = {}
    for e in cfg.get("overrides", {}).get("setnames", []):
        names[tuple(e["point"])] = e["name"]
    sets = []
    for k, ln in enumerate(lines):
        box = [ln["x0"], ln["y0"], ln["x1"] - ln["x0"], ln["bottom"] - ln["y0"]]
        name = None
        for (px, py), nm in names.items():
            if box[0] - 2 <= px < box[0] + box[2] + 2 and box[1] - 2 <= py < box[1] + box[3] + 2:
                name = nm
        sets.append({"id": k, "box": box, "point": [box[0] + box[2] // 2, box[1] + box[3] // 2],
                     "name": config.slug(name) if name else None})
    return sets


def assign_sets(segs, sets):
    """Rattache chaque SEGMENT de rangée (sprites consécutifs, coupés aux trous) à une légende, par
    ordre de priorité :
    1. légende sur la même rangée, juste à gauche du segment ;
    2. légende sur la même rangée, juste à droite ;
    3. légende au-dessus : parmi les plus basses (à 8 px près), celle qui COMMENCE au-dessus du segment
       (entre son début et sa fin), sinon la plus proche à sa gauche.
    Corrections manuelles : sk setbox."""
    live = [st for st in sets if st["name"] != "none"]
    for seg in segs:
        x0 = min(i["x"] for i in seg); x1 = max(i["x"] + i["w"] for i in seg)
        y0 = min(i["y"] for i in seg); y1 = max(i["y"] + i["h"] for i in seg)
        cy = (y0 + y1) / 2
        side, above = None, []
        for st in live:
            x, y, w, h = st["box"]
            same_band = y <= y1 + 4 and y + h >= y0 - 4 and abs((y + h / 2) - cy) <= max(y1 - y0, 16)
            if same_band and x + w <= x0 + 2:
                key = (2, -(x0 - (x + w)))
            elif same_band and x >= x1 - 2:
                key = (1, -(x - x1))
            else:
                if y + h <= y0 + 4 and x <= x1:
                    above.append(st)
                continue
            if side is None or key > side[0]:
                side = (key, st["id"])
        sid = side[1] if side else None
        if sid is None and above:
            low = max(st["box"][1] + st["box"][3] for st in above)
            level = [st for st in above if st["box"][1] + st["box"][3] >= low - 8]
            inside = [st for st in level if x0 - 8 <= st["box"][0] <= x1]
            if inside:
                sid = min(inside, key=lambda st: st["box"][0])["id"]
            else:
                sid = max(level, key=lambda st: st["box"][0])["id"]  # la plus proche à gauche
        if sid is not None:
            for it in seg:
                it["set"] = sid


def apply_setbox(kept, sets, ov):
    """sk setbox : tout sprite dont le centre est dans la boîte rejoint l'ensemble désigné."""
    for e in ov.get("setbox", []):
        px, py = e["set_point"]
        st = next((s_ for s_ in sets if s_["box"][0] - 2 <= px < s_["box"][0] + s_["box"][2] + 2
                   and s_["box"][1] - 2 <= py < s_["box"][1] + s_["box"][3] + 2), None)
        if st is None:
            continue
        bx, by, bw, bh = e["box"]
        for it in kept:
            if bx <= it["x"] + it["w"] / 2 < bx + bw and by <= it["y"] + it["h"] / 2 < by + bh:
                it["set"] = st["id"]


def group_anim(a, rows, p):
    """Animations (effets, monstres, persos hors gabarit Pokémon) : frames rangées en ligne, coupées aux
    trous (row_split_gap) puis là où la palette change nettement (Jaccard < anim_split_sim) : c'est en
    général le passage à un autre effet. Les groupes d'une seule frame restent des items isolés."""
    ents = []
    for r in rows:
        for seg in segments(r["items"], p["row_split_gap"]):
            pals = [_palette(a, it) for it in seg]
            cur = [seg[0]]
            for i in range(1, len(seg)):
                if seg[i].get("cut") or _jaccard(pals[i - 1], pals[i]) < p["anim_split_sim"]:
                    ents.append(cur); cur = []
                cur.append(seg[i])
            ents.append(cur)
    return [e for e in ents if len(e) >= 2]


def force_entities(ent_all, kept, cfg, sheet_p):
    """sk entity : ces items (dans cet ordre) forment UNE entité ; ils sont retirés des entités
    automatiques (une entité automatique réduite à 1 frame redevient un item isolé)."""
    forced = []
    for pts in cfg.get("overrides", {}).get("entities", []):
        frames = []
        for x, y in pts:
            it = _at(kept, x, y)
            if it and it not in frames:
                frames.append(it)
        if frames:
            forced.append(frames)
    if not forced:
        return ent_all
    taken = {id(f) for fr in forced for f in fr}
    out = []
    for frames, p in ent_all:
        rest = [f for f in frames if id(f) not in taken]
        if len(rest) >= 2:
            out.append((rest, p))
    p0 = sheet_p
    return out + [(fr, p0) for fr in forced]


def check_palettes(a, entities):
    """Idée 4 : une frame dont les couleurs ne se retrouvent presque pas dans les autres frames de
    l'entité appartient sûrement à un autre personnage."""
    warnings = []
    for ei, frames in enumerate(entities):
        if len(frames) < 3:
            continue
        pals = [_palette(a, f) for f in frames]
        for fi, pf in enumerate(pals):
            if len(pf) < 4:
                continue
            others = set().union(*(q for k, q in enumerate(pals) if k != fi))
            share = len(pf & others) / len(pf)
            if share < 0.5:
                f = frames[fi]
                warnings.append({"flag": "mixed_entity", "x": f["x"], "y": f["y"], "item": f.get("id"),
                                 "msg": f"entité e{ei} frame {fi} : seulement {share:.0%} de ses couleurs dans les "
                                        "autres frames -> autre personnage mélangé ? (cut / row_split_gap)"})
    return warnings


def _row_lift(frames):
    """Pour chaque frame : hauteur (px) de son bas au-dessus du bas de SA rangée de la feuille."""
    order = sorted(range(len(frames)), key=lambda i: frames[i]["y"] + frames[i]["h"] / 2)
    rows, cur, cur_lo, cur_hi = [], [], None, None
    for i in order:
        f = frames[i]
        lo, hi = f["y"], f["y"] + f["h"]
        if cur and min(hi, cur_hi) - max(lo, cur_lo) > 0.5 * min(f["h"], cur_hi - cur_lo):
            cur.append(i); cur_lo, cur_hi = min(cur_lo, lo), max(cur_hi, hi)
        else:
            if cur:
                rows.append(cur)
            cur, cur_lo, cur_hi = [i], lo, hi
    if cur:
        rows.append(cur)
    lift = [0] * len(frames)
    for r in rows:
        base = max(frames[i]["y"] + frames[i]["h"] for i in r)
        for i in r:
            lift[i] = base - (frames[i]["y"] + frames[i]["h"])
    return lift


def layout_frames(frames, p):
    """Position de chaque frame dans une case commune. Renvoie (cell_w, cell_h, [(dx, dy)])."""
    cells = {tuple(f["cell"][2:]) for f in frames if "cell" in f}
    if len(cells) == 1 and all("cell" in f for f in frames) and p["cell"] in ("auto", "sheet"):
        # grille : la position dans la case EST l'alignement d'origine ; on rogne le vide commun
        rel = [(f["x"] - f["cell"][0], f["y"] - f["cell"][1]) for f in frames]
        mx, my = min(r[0] for r in rel), min(r[1] for r in rel)
        cw = max(r[0] + f["w"] for r, f in zip(rel, frames)) - mx
        ch = max(r[1] + f["h"] for r, f in zip(rel, frames)) - my
        return cw, ch, [(r[0] - mx, r[1] - my) for r in rel]
    if p["anchor"] == "center":
        cw = max(f["w"] for f in frames); ch = max(f["h"] for f in frames)
        offs = [((cw - f["w"]) // 2, (ch - f["h"]) // 2) for f in frames]
    else:
        # "bottom" : pieds alignés ; horizontalement on garde le décalage d'origine dans la case
        # si les frames suivent un pas régulier, sinon on centre.
        xs = [f["x"] for f in frames]
        cxs = [f["x"] + f["w"] / 2 for f in frames]
        regular = False
        if len(frames) >= 3:
            pitch = np.median(np.diff(cxs))
            slots = [cxs[0] + i * pitch for i in range(len(frames))]
            regular = pitch > 0 and max(abs(c - s) for c, s in zip(cxs, slots)) <= 2.5
        if regular:
            rel = [xs[i] - (cxs[0] + i * pitch) for i in range(len(frames))]
            m = min(rel)
            dxs = [int(round(r - m)) for r in rel]
        else:
            wmax = max(f["w"] for f in frames)
            dxs = [(wmax - f["w"]) // 2 for f in frames]
        cw = max(dx + f["w"] for dx, f in zip(dxs, frames))
        # revue C4 : ligne de base PAR RANGÉE de la feuille (frames dont les hauteurs se chevauchent), pas
        # une seule pour toute l'entité : sinon des frames prises sur plusieurs rangées (group=blocks,
        # sk entity) gardent leur décalage vertical d'origine et l'animation marche « en escalier ».
        # Dans une rangée, le petit rebond d'origine (frame plus haute d'1-2 px) est conservé.
        lift = _row_lift(frames)
        ch = max(f["h"] + l for f, l in zip(frames, lift))
        offs = [(dx, ch - f["h"] - l) for dx, f, l in zip(dxs, frames, lift)]
    if p["cell"] not in ("auto", "sheet"):
        fw, fh = map(int, p["cell"].lower().split("x"))
        ox, oy = (fw - cw) // 2, fh - ch if p["anchor"] != "center" else (fh - ch) // 2
        offs = [(dx + ox, dy + oy) for dx, dy in offs]
        cw, ch = fw, fh
    return cw, ch, offs


# ---------------------------------------------------------------- zones / parties

def parts_of(cfg, shape):
    """Découpe la feuille en parties : chaque zone manuelle (dans l'ordre), puis le reste.
    Renvoie [(index_zone ou None, masque bool, réglages fusionnés, zone)]."""
    p = config.params(cfg)
    h, w = shape
    taken = np.zeros((h, w), bool)
    parts = []
    for zi, z in enumerate(cfg.get("zones", [])):
        x, y, zw, zh = z["box"]
        m = np.zeros((h, w), bool)
        m[max(0, y):max(0, y + zh), max(0, x):max(0, x + zw)] = True
        m &= ~taken
        taken |= m
        parts.append((zi, m, {**p, **z.get("params", {})}, z))
    parts.append((None, ~taken, p, None))
    return parts


def _in_part(pt, zi, cfg):
    """Zone d'appartenance d'un point (la première zone qui le contient), None = reste."""
    for k, z in enumerate(cfg.get("zones", [])):
        x, y, w, h = z["box"]
        if x <= pt[0] < x + w and y <= pt[1] < y + h:
            return k == zi
    return zi is None


def _filter_overrides(ov, zi, cfg):
    out = {}
    for k, v in ov.items():
        if k == "merge":
            out[k] = [g for g in v if g and _in_part(g[0], zi, cfg)]
        elif k in ("add", "carve"):
            out[k] = [b for b in v if _in_part((b[0] + b[2] // 2, b[1] + b[3] // 2), zi, cfg)]
        elif k == "names":
            out[k] = [e for e in v if _in_part(e["point"], zi, cfg)]
        elif k in ("drop", "keep", "split", "cut"):
            out[k] = [pt for pt in v if _in_part(pt, zi, cfg)]
        # setnames, setbox, entities : appliqués au niveau de la feuille entière (run), pas par partie
    return out


def _detect_part(a_full, mask, p, cfg, zi, split_done):
    a = a_full.copy()
    a[~mask] = 0
    lab, n = imageops.components(a, p["gap"])
    lab_fine, _ = imageops.components(a, 0) if p["gap"] > 0 else (lab, n)
    items = imageops.describe(a, lab, n)
    for it in items:
        it["labels"] = [("g", it.pop("label"))]
        it["zone"] = zi
        if max(it["w"], it["h"]) < p["min_size"] or it["area"] < p["min_area"]:
            it["kind"] = "tiny"
    if p["drop_text"]:
        sprites = [it for it in items if it["kind"] == "sprite"]
        imageops.mark_text(sprites, p["text_max_h"])
        _mark_panels(sprites, a, lab, p.get("panel_frames"))
    if p["drop_junk"]:
        imageops.mark_junk([it for it in items if it["kind"] == "sprite" and not it.get("panel_frame")], a, lab, cfg["category"])
    lab_cells = np.zeros(a.shape[:2], np.int32)
    grid_report = []
    if p["layout"] in ("auto", "grid"):
        kept = {it["labels"][0][1] for it in items if it["kind"] == "sprite"}
        gmask = np.isin(lab, list(kept)) if kept else np.zeros(a.shape[:2], bool)
        gp = dict(p, grid_min_conf=0.0) if p["layout"] == "grid" else p
        items, lab_cells, grid_report = grid.apply(a, items, gp, gmask)
        for it in items:
            it.setdefault("zone", zi)
        if p["drop_text"] and any(r.get("mode") in ("grille", "xycut") for r in grid_report):
            # la grille peut séparer des mots soudés en lettres : on refait passer le détecteur de texte
            imageops.mark_text([it for it in items if it["kind"] == "sprite"], p["text_max_h"])
    lab_carve = np.zeros(a.shape[:2], np.int32)
    labs = (lab, lab_fine, lab_cells, lab_carve)
    for it in items:
        it["_labs"] = labs
        it["_a"] = a
    carve_log = _carve(items, a, labs, cfg.get("overrides", {}).get("carve", []), zi, cfg)
    # 2026-10-30 : seulement les points de CETTE partie (zone) : un point d'une zone tombait aussi dans la
    # boîte d'un grand cadre de la partie principale, re-découpé en double avec tout ce qu'il entoure (8183)
    splits = [pt for pt in cfg.get("overrides", {}).get("split", []) if _in_part(pt, zi, cfg)]
    log = carve_log + apply_split(items, splits, lab_fine, labs, split_done, bool(p.get("split_own")))
    for r in grid_report:
        r["zone"] = zi
    return items, {"override_log": log, "grid": grid_report}


def _carve(items, a, labs, rects, zi, cfg):
    """Découpe rectangulaire (sk carve) : les pixels opaques du rectangle deviennent UN item, retirés
    des items qui les contenaient. Sert quand des sprites se touchent au pixel près."""
    lab, lab_fine, lab_cells, lab_carve = labs
    log = []
    for k, (x, y, w, h) in enumerate(rects, start=1):
        if not _in_part((x + w // 2, y + h // 2), zi, cfg):
            continue
        H, W = a.shape[:2]
        x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
        sel = np.zeros((y1 - y0, x1 - x0), bool)
        for it in list(items):
            if it["x"] >= x1 or it["x"] + it["w"] <= x0 or it["y"] >= y1 or it["y"] + it["h"] <= y0:
                continue
            removed = False
            for kind, lb in it["labels"]:
                arr = {"g": lab, "f": lab_fine, "c": lab_cells, "k": lab_carve}[kind]
                m = arr[y0:y1, x0:x1] == lb
                if m.any():
                    sel |= m
                    arr[y0:y1, x0:x1][m] = 0
                    removed = True
            if removed:
                px = _pixels(a, it)
                ys, xs = np.nonzero(px[..., 3] > 0)
                if not len(xs):
                    items.remove(it)
                else:
                    it["x"], it["y"] = it["x"] + int(xs.min()), it["y"] + int(ys.min())
                    it["w"], it["h"] = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
        if not sel.any():
            log.append(f"carve {x},{y},{w},{h} : rien à découper"); continue
        lab_carve[y0:y1, x0:x1][sel] = k
        ys, xs = np.nonzero(sel)
        items.append({"x": x0 + int(xs.min()), "y": y0 + int(ys.min()), "w": int(xs.max() - xs.min() + 1),
                      "h": int(ys.max() - ys.min() + 1), "labels": [("k", k)], "area": int(sel.sum()),
                      "ncolors": 0, "dominant": "", "dom_frac": 0, "kind": "sprite", "zone": zi,
                      "_labs": labs, "_a": a})
    return log


BG_KEYS = {"bg", "bg_tol", "bg_mode", "black_bg", "peel", "peel_min_area"}


def detect(cfg):
    """Analyse sans écrire : renvoie (rgba, parties, infos). Chaque partie = (zi, réglages, items)."""
    p = config.params(cfg)
    src = os.path.join(config.PROJECT, cfg["src"])
    raw = Image.open(src).convert("RGBA")
    ov = cfg.get("overrides", {})
    raw_arr = np.array(raw)
    if any((e.get("fill") or "clear") != "clear" for e in ov.get("erase", [])):
        raw = Image.fromarray(imageops.erase_fill(raw_arr, ov["erase"]))  # texte effacé AVANT le retrait du fond
    a, bginfo = imageops.remove_background(raw, p)
    imageops.post_ops(a, raw_arr, ov)
    display = a.copy()  # image montrée sur les planches (avec les fonds propres aux zones)
    out, info = [], {"bg": bginfo, "override_log": [], "grid": [], "zones": []}
    split_done = set()
    for zi, mask, pp, z in parts_of(cfg, a.shape[:2]):
        if z is not None:
            info["zones"].append({"zone": zi, "box": z["box"], "skip": bool(z.get("skip")), "params": z.get("params", {})})
        if z is not None and z.get("skip"):
            continue
        a_part = a
        if z is not None and BG_KEYS & set(z.get("params", {})):
            # fond propre à la zone : retrait refait sur le seul rectangle de la zone, avec ses réglages
            x, y, w, h = z["box"]
            a_part = a.copy()
            crop, zinfo = imageops.remove_background(raw.crop((x, y, x + w, y + h)), pp)
            H, W = a.shape[:2]
            a_part[max(0, y):min(H, y + h), max(0, x):min(W, x + w)] = crop[:min(H, y + h) - max(0, y), :min(W, x + w) - max(0, x)]
            imageops.post_ops(a_part, raw_arr, ov)
            display[mask] = a_part[mask]
            info["zones"][-1]["bg"] = zinfo["removed"]
        items, inf = _detect_part(a_part, mask, pp, cfg, zi, split_done)
        info["override_log"] += inf["override_log"]
        info["grid"] += inf["grid"]
        out.append((zi, pp, items))
    info["override_log"] += [f"split ({x},{y}) : aucun item" for x, y in ov.get("split", []) if (x, y) not in split_done]
    # corrections sur la feuille entière, puis redistribution des items dans leur partie
    flat = [it for _, _, items in out for it in items]
    info["override_log"] += apply_global(flat, ov)
    out = [(zi, pp, [it for it in flat if it.get("zone") == zi]) for zi, pp, _ in out]
    return display, out, info


def _mark_panels(sprites, a, lab, panel_frames=False):
    """panel_frames : chaque encadré plein est une FRAME (effet plein écran, météo : un écran par case) ; sa
    couleur de fond devient transparente, son contenu (gouttes, flocons) reste, à sa place dans la case."""
    live = [it for it in sprites if it["kind"] == "sprite"]
    tmp = [dict(it, label=it["labels"][0][1]) for it in live]
    imageops.mark_panels(tmp, a, lab)
    for it, t in zip(live, tmp):
        if t["kind"] == "panel" and panel_frames:
            x, y, w, h = it["x"], it["y"], it["w"], it["h"]
            box = a[y:y + h, x:x + w]
            m = lab[y:y + h, x:x + w] == it["labels"][0][1]
            border = np.concatenate([box[0, :, :3], box[-1, :, :3], box[:, 0, :3], box[:, -1, :3]])
            fill = Counter(map(tuple, border.tolist())).most_common(1)[0][0]
            box[m & (box[..., :3] == fill).all(-1), 3] = 0
            it["panel_frame"] = True
            continue
        it["kind"] = t["kind"]


def _pixels(a, item):
    if "_px" in item:  # item fusionné : pixels déjà assemblés
        return item["_px"].copy()
    lab, lab_fine, lab_cells, lab_carve = item["_labs"]
    a = item.get("_a", a)  # une zone peut avoir son propre retrait de fond
    x, y, w, h = item["x"], item["y"], item["w"], item["h"]
    sub = a[y:y + h, x:x + w].copy()
    keep = np.zeros((h, w), bool)
    for kind, lb in item["labels"]:
        src = {"g": lab, "f": lab_fine, "c": lab_cells, "k": lab_carve}[kind]
        keep |= src[y:y + h, x:x + w] == lb
    sub[~keep] = 0
    return sub


def _mirrors(arrs):
    """Idée 7 : pour chaque image, index d'une image précédente identique (duplicate_of) ou
    identique une fois retournée horizontalement (mirror_of)."""
    seen, out = {}, []
    for i, px in enumerate(arrs):
        key = px.tobytes() + bytes(str(px.shape), "ascii")
        flip = np.ascontiguousarray(px[:, ::-1])
        fkey = flip.tobytes() + bytes(str(flip.shape), "ascii")
        rel = {}
        if key in seen:
            rel["duplicate_of"] = seen[key]
        elif fkey in seen and fkey != key:
            rel["mirror_of"] = seen[fkey]
        seen.setdefault(key, i)
        out.append(rel)
    return out


def _clean(it):
    return {k: v for k, v in it.items() if k not in ("labels", "_labs", "_a", "_px")}


def run(cfg, write=True):
    a, parts, info = detect(cfg)
    base = config.slug(cfg["title"])
    ordered_all, others_all, ent_all, warnings = [], [], [], []
    sheet_p = config.params(cfg)
    staged = []
    for zi, p, items in parts:
        kept = [it for it in items if it["kind"] == "sprite"]
        rows = reading_order(kept, p["row_tol"])
        staged.append((zi, p, items, kept, rows))
    sets = []
    if sheet_p["sets"] == "captions":
        sets = caption_sets([it for _, _, items, _, _ in staged for it in items], cfg)
        all_kept = [it for _, _, _, kept, _ in staged for it in kept]
        segs = [seg for _, p_, _, _, rows in staged for r in rows for seg in segments(r["items"], p_["row_split_gap"])]
        assign_sets(segs, sets)
        apply_setbox(all_kept, sets, cfg.get("overrides", {}))
    for zi, p, items, kept, rows in staged:
        ordered = [it for r in rows for it in r["items"]]
        ordered_all += ordered
        others_all += [it for it in items if it["kind"] != "sprite"]
        if p["group"] in ("rows", "chunks"):
            ents, w = group_entities(rows, p)
            warnings += w
        elif p["group"] in ("columns", "columns_all"):
            ents, w = group_columns(ordered, p)
            warnings += w
        elif p["group"] == "blocks":
            ents, w = group_blocks(rows, ordered, p)
            warnings += w
        elif p["group"] == "palette":
            ents = group_by_palette(a, ordered, p)
        elif p["group"] == "anim":
            ents = group_anim(a, rows, p)
        else:
            ents = []
        warnings += check_palettes(a, ents)
        ent_all += [(e, p) for e in ents]
    ent_all = force_entities(ent_all, ordered_all, cfg, sheet_p)
    others_all.sort(key=lambda it: (it["y"], it["x"]))
    for i, it in enumerate(ordered_all + others_all):
        it["id"] = i

    result = {"sheet": cfg["id"], "params": sheet_p, "info": info, "warnings": warnings, "items": [], "entities": [],
              "sets": sets}
    out = config.out_dir(cfg)
    if write:
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out, exist_ok=True)
    folder = {st["id"]: (st["name"] or f"set_{st['id']:02d}") for st in sets}

    def place(it_or_frames, fname):
        """Chemin relatif du fichier : sous-dossier de l'ensemble s'il y en a un."""
        sid = it_or_frames.get("set") if isinstance(it_or_frames, dict) else it_or_frames[0].get("set")
        rel = os.path.join(folder[sid], fname) if sid is not None else fname
        if write:
            os.makedirs(os.path.dirname(os.path.join(out, rel)) or out, exist_ok=True)
        return rel

    grouped_ids = set()
    if ent_all:
        sheet_cell = None
        if sheet_p["cell"] == "sheet":
            dims = [layout_frames(e, dict(p, cell="auto"))[:2] for e, p in ent_all]
            sheet_cell = f"{max(d[0] for d in dims)}x{max(d[1] for d in dims)}"
        for ei, (frames, p) in enumerate(ent_all):
            pp = dict(p, cell=sheet_cell) if sheet_cell else p
            cw, ch, offs = layout_frames(frames, pp)
            strip = np.zeros((ch, cw * len(frames), 4), np.uint8)
            framepx = []
            for fi, (f, (dx, dy)) in enumerate(zip(frames, offs)):
                px = _pixels(a, f)
                x0, y0 = fi * cw + dx, dy
                region = strip[y0:y0 + f["h"], x0:x0 + f["w"]]
                m = px[..., 3] > 0
                region[m] = px[m]
                framepx.append(strip[:, fi * cw:(fi + 1) * cw].copy())
                grouped_ids.add(f["id"])
            rels = _mirrors(framepx)
            sid = frames[0].get("set")
            prefix = folder[sid] if sid is not None else base
            name = next((f["name"] for f in frames if f.get("name")), None) or f"{prefix}_e{ei:03d}"
            fname = place(frames, f"{name}.png")
            if write:
                Image.fromarray(strip).save(os.path.join(out, fname))
            anims = None  # animations nommées posées par `sk anims` (ancrées sur un point d'une frame)
            for entry in cfg.get("overrides", {}).get("anims", []):
                px_, py_ = entry["point"]
                if any(f["x"] <= px_ < f["x"] + f["w"] and f["y"] <= py_ < f["y"] + f["h"] for f in frames):
                    anims = {k: [i for i in v if 0 <= i < len(frames)] for k, v in entry["map"].items()}
            result["entities"].append({
                "id": ei, "name": name, "file": fname, "cell": [cw, ch], "zone": frames[0].get("zone"),
                **({"animations": anims} if anims else {}),
                "set": frames[0].get("set"),
                "template": p["template"],
                "frames": [{"item": f["id"], "role": r, "src": [f["x"], f["y"], f["w"], f["h"]], **rel}
                           for f, r, rel in zip(frames, templates.roles(p["template"], len(frames)), rels)],
                "box": [min(f["x"] for f in frames), min(f["y"] for f in frames),
                        max(f["x"] + f["w"] for f in frames) - min(f["x"] for f in frames),
                        max(f["y"] + f["h"] for f in frames) - min(f["y"] for f in frames)],
            })
    # items isolés : tout sprite qui n'appartient à aucune entité
    loose = [it for it in ordered_all if it["id"] not in grouped_ids]
    pxs = [_pixels(a, it) for it in loose]
    for it, px, rel in zip(loose, pxs, _mirrors(pxs)):
        prefix = folder[it["set"]] if it.get("set") is not None else base
        name = it.get("name") or f"{prefix}_{it['id']:03d}"
        it["file"] = place(it, f"{name}.png")
        it.update(rel)
        if write:
            Image.fromarray(px).save(os.path.join(out, it["file"]))
    result["items"] = [_clean(it) for it in ordered_all + others_all]

    if write:
        manifest = {"sheet": cfg["id"], "game": cfg["game"], "category": cfg["category"],
                    "title": cfg["title"], "type": cfg["type"], "template": sheet_p["template"],
                    "validation": "pending",
                    "sets": [dict(st, folder=folder[st["id"]]) for st in sets],
                    "entities": result["entities"],
                    "items": [it for it in result["items"] if it["kind"] == "sprite" and "file" in it]}
        config.write_json_atomic(os.path.join(out, "manifest.json"), manifest, indent=1)
        qa = os.path.join(config.QA_DIR, cfg["id"])
        os.makedirs(qa, exist_ok=True)
        from . import auto, checks
        # revue I6 : la numérotation des items est liée à l'état de la fiche qui l'a produite
        config.write_json_atomic(os.path.join(qa, "last_run.json"), dict(result, state=checks.state(cfg)))
        # une feuille validée dont la fiche n'a pas changé depuis ses confirmations le reste ; needs_fix /
        # skip sont des conclusions : un run de diagnostic ne les efface pas (revue I7)
        keep = cfg["status"] in ("auto_ok", "needs_fix", "skip") or (cfg["status"] == "ok" and not checks.missing(cfg))
        if not keep:
            cfg["status"] = "extracted"
        cfg["run_state"] = checks.state(cfg)
        config.save(cfg)
        auto.refresh_marker(cfg)  # revue C3 : le rmtree a effacé NON_VERIFIE.txt / A_VERIFIER.txt
    result["_arrays"] = (a,)
    return result
