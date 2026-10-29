"""Tables d'autotiles de Donjon Mystère (feuilles « Ripped and formatted by SilverDeoxys563 »).

Format : un tableau à cases de 24 px séparées par des lignes de 1 px (cyan #80FFFF ou rose #FF80FF), pas 25.
Colonnes par groupes de 3 : « Legend », puis Walls, Wall Alt. 1, Wall Alt. 2, Ground, Ground Alt., Water…
Chaque case de la légende est un motif 3x3 de carrés de 8 px : carré plein = voisin du MÊME terrain dans cette
direction (le centre = la tuile elle-même). La tuile à la même rangée et à la même colonne relative d'un groupe
est la variante de ce terrain pour ce voisinage : exactement les « peering bits » d'un terrain Godot (3x3).

Sorties : rpg/assets/pmd_red/terrains/<titre>/<groupe>.png (atlas : la grille du tableau sans séparateurs)
+ terrains.json (pour chaque tuile de l'atlas : colonne, rangée, masque des 8 voisins).
"""
import json
import os
from collections import Counter

import numpy as np
from PIL import Image, ImageDraw

from . import config

LINE_COLORS = [(128, 255, 255), (255, 128, 255)]
PITCH = 25
T = 24
DIRS8 = [("NW", 0, 0), ("N", 0, 1), ("NE", 0, 2), ("W", 1, 0), ("E", 1, 2), ("SW", 2, 0), ("S", 2, 1), ("SE", 2, 2)]
DEFAULT_GROUPS = {
    6: ["walls", "wall_alt_1", "wall_alt_2", "ground", "ground_alt", "water"],
    5: ["walls", "wall_alt_1", "wall_alt_2", "ground", "water"],
    7: ["walls", "wall_alt_1", "wall_alt_2", "ground", "ground_alt", "water", "water_sparkle"],
    8: ["walls", "wall_alt_1", "wall_alt_2", "ground", "ground_alt_1", "ground_alt_2", "water", "water_sparkle"],
    9: ["walls", "wall_alt_1", "wall_alt_2", "ground", "ground_alt", "ground_alt_2", "water", "water_alt", "water_alt_2"],
}


def _line_mask(a):
    m = np.zeros(a.shape[:2], bool)
    for c in LINE_COLORS:
        m |= (a[..., :3] == c).all(-1)
    return m


def _lines(counts, min_len):
    return [i for i, n in enumerate(counts) if n >= min_len]


def parse(a):
    """Renvoie la structure du tableau ou None si ce n'est pas une table PMD formatée."""
    lm = _line_mask(a)
    xs = _lines(lm.sum(0), 150)
    ys = _lines(lm.sum(1), 150)
    if len(xs) < 7 or len(ys) < 4:
        return None
    if Counter(np.diff(xs).tolist()).most_common(1)[0][0] != PITCH or Counter(np.diff(ys).tolist()).most_common(1)[0][0] != PITCH:
        return None
    x0, y0 = xs[0], ys[0]
    # cases : de la première ligne jusqu'au bout du tableau (la dernière ligne peut manquer au bord)
    ncols = (min(a.shape[1] - 1, xs[-1] + PITCH) - x0) // PITCH
    nrows = (ys[-1] - y0) // PITCH
    # en-tête : une rangée au-dessus de la première ligne ; les séparateurs de groupes la traversent
    hy = y0 - PITCH // 2
    bounds = [x for x in range(x0, x0 + ncols * PITCH + 1, PITCH) if 0 <= hy and x < a.shape[1] and lm[max(0, hy - 3):hy + 3, x].any()]
    groups = []
    for gx0, gx1 in zip(bounds, bounds[1:]):
        c0, c1 = (gx0 - x0) // PITCH, (gx1 - x0) // PITCH
        if c1 > c0:
            groups.append((c0, c1))
    if not groups or groups[0][0] != 0:
        # en-tête illisible : légende = 3 colonnes, puis groupes de 3
        groups = [(c, min(c + 3, ncols)) for c in range(0, ncols, 3)]
    return {"x0": x0, "y0": y0, "ncols": ncols, "nrows": nrows, "groups": groups}


def cell(a, tb, r, c):
    x, y = tb["x0"] + 1 + c * PITCH, tb["y0"] + 1 + r * PITCH
    return a[y:y + T, x:x + T]


def _bg(a, tb):
    """Couleur de fond des cases vides (la plus fréquente dans les cases)."""
    cnt = Counter()
    for r in range(0, tb["nrows"], 2):
        for c in range(0, tb["ncols"], 2):
            px = cell(a, tb, r, c)
            cnt[tuple(px[T // 2, T // 2, :3].tolist())] += 1
    return cnt.most_common(1)[0][0]


def legend_mask(px, bg):
    """Motif 3x3 d'une case de légende : True = carré plein (pas la couleur de fond)."""
    m = np.zeros((3, 3), bool)
    for i in range(3):
        for j in range(3):
            sq = px[i * 8 + 2:i * 8 + 6, j * 8 + 2:j * 8 + 6, :3]
            m[i, j] = (sq != bg).any(-1).mean() > 0.5
    return m


MAGENTA = (255, 0, 255)


def _fix_magenta(px, overlay):
    """Magenta #FF00FF = couleur de transparence du ripper. Groupe « sparkle » (reflets posés par-dessus
    l'eau) : transparent. Ailleurs (pixels animés marqués dans l'eau) : remplacé par la couleur voisine."""
    m = (px[..., :3] == MAGENTA).all(-1)
    if not m.any():
        return px
    px = px.copy()
    if overlay or m.mean() > 0.5:
        px[m] = 0
        return px
    from scipy import ndimage
    _, (iy, ix) = ndimage.distance_transform_edt(m, return_indices=True)
    px[m] = px[iy[m], ix[m]]
    return px


def extract(cfg, write=True):
    from . import imageops
    a = np.array(Image.open(os.path.join(config.PROJECT, cfg["src"])).convert("RGBA"))
    ov = cfg.get("overrides", {})
    tb = parse(a)  # structure lue AVANT les retouches (une gomme ne doit pas effacer les lignes du tableau)
    raw = a.copy()
    if any((e.get("fill") or "clear") != "clear" for e in ov.get("erase", [])):
        a = imageops.erase_fill(raw, ov["erase"])
    a = imageops.post_ops(a, raw, ov)  # sk erase (clear) / sk flood : pixels rendus transparents
    if tb is None:
        return None
    bg = _bg(a, tb)
    leg_c0, leg_c1 = tb["groups"][0]
    data_groups = tb["groups"][1:]
    names = (cfg.get("params", {}).get("pmd_groups") or DEFAULT_GROUPS.get(len(data_groups))
             or [f"group_{k + 1}" for k in range(len(data_groups))])
    names = list(names) + [f"group_{k + 1}" for k in range(len(names), len(data_groups))]
    masks = {}
    for r in range(tb["nrows"]):
        for c in range(leg_c0, leg_c1):
            px = cell(a, tb, r, c)
            if (px[..., :3] == bg).all(-1).mean() > 0.97:
                continue
            masks[(r, c - leg_c0)] = legend_mask(px, bg)
    out_groups = []
    out = os.path.join(config.ASSETS, cfg["game"], "terrains", config.slug(cfg["title"]))
    if write:
        os.makedirs(out, exist_ok=True)
    for name, (c0, c1) in zip(names, data_groups):
        w = c1 - c0
        atlas = np.zeros((tb["nrows"] * T, w * T, 4), np.uint8)
        cells = []
        for r in range(tb["nrows"]):
            for k in range(w):
                px = cell(a, tb, r, c0 + k)
                empty = (px[..., :3] == bg).all(-1).mean() > 0.97 or (px[..., 3] == 0).mean() > 0.97
                if empty:
                    continue
                atlas[r * T:(r + 1) * T, k * T:(k + 1) * T] = _fix_magenta(px, "sparkle" in name)
                m = masks.get((r, k))
                cells.append({"col": k, "row": r,
                              "mask": None if m is None else {d: bool(m[i, j]) for d, i, j in DIRS8}})
        if not cells:
            continue
        g = {"name": name, "file": f"{name}.png", "cols": w, "rows": tb["nrows"], "tiles": cells,
             "sans_legende": sum(1 for x in cells if x["mask"] is None)}
        out_groups.append(g)
        if write:
            Image.fromarray(atlas).save(os.path.join(out, g["file"]))
    res = {"sheet": cfg["id"], "title": cfg["title"], "tile": T, "table": tb, "groups": out_groups,
           "legend_cells": len(masks)}
    if write:
        config.write_json_atomic(os.path.join(out, "terrains.json"), res, indent=1)
        res["dir"] = out
    return res


def montage(cfg, res, scale=2):
    """Planche : en haut l'en-tête du tableau d'origine (pour lire les noms des colonnes), puis pour chaque
    groupe extrait : son nom et ses tuiles, avec à gauche de chaque rangée le motif de légende décodé."""
    from .qa import _checker, _font
    font = _font(14)
    a = Image.open(os.path.join(config.PROJECT, cfg["src"])).convert("RGBA")
    tb = res["table"]
    head = a.crop((tb["x0"], max(0, tb["y0"] - PITCH), tb["x0"] + tb["ncols"] * PITCH, tb["y0"] + 1))
    head = head.resize((head.width * scale, head.height * scale), Image.NEAREST)
    blocks = []
    for g in res["groups"]:
        im = Image.open(os.path.join(res["dir"], g["file"])).convert("RGBA")
        blocks.append((g, im.resize((im.width * scale, im.height * scale), Image.NEAREST)))
    mini = 3 * 4 + 6
    W = max(head.width, sum(b.width + mini + 30 for _, b in blocks)) + 20
    H = head.height + 40 + max(b.height for _, b in blocks) + 30
    sheet = Image.new("RGBA", (W, H), (50, 50, 60, 255))
    d = ImageDraw.Draw(sheet)
    sheet.alpha_composite(head, (10, 6))
    d.text((10, head.height + 10), "en-tete d'origine (noms des colonnes) ; dessous : groupes extraits avec "
                                   "le motif de voisins decode (blanc = meme terrain)", fill=(220, 220, 220), font=font)
    x = 10
    y0 = head.height + 34
    for g, im in blocks:
        d.text((x, y0), g["name"], fill=(255, 255, 120), font=font)
        sheet.alpha_composite(_checker(im.width, im.height, 6), (x + mini, y0 + 18))
        sheet.alpha_composite(im, (x + mini, y0 + 18))
        for t in g["tiles"]:
            if t["col"] == 0 and t["mask"]:
                my = y0 + 18 + t["row"] * T * scale + 4
                for dn, i, j in DIRS8 + [("C", 1, 1)]:
                    on = t["mask"].get(dn, True)
                    d.rectangle((x + j * 4, my + i * 4, x + j * 4 + 3, my + i * 4 + 3),
                                fill=(255, 255, 255) if on else (90, 90, 100))
        x += im.width + mini + 30
    outd = os.path.join(config.QA_DIR, cfg["id"])
    os.makedirs(outd, exist_ok=True)
    paths = []
    for k, py in enumerate(range(0, H, 1400)):
        p = os.path.join(outd, f"terrains_{k}.png")
        sheet.crop((0, py, W, min(H, py + 1400))).save(p)
        paths.append(p)
    return paths
