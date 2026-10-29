"""Retrait du fond, détection des composantes, détection du texte et des encarts."""
from collections import Counter

import numpy as np
from PIL import Image
from scipy import ndimage

EIGHT = np.ones((3, 3), bool)


def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(c) -> str:
    return "#%02X%02X%02X" % tuple(int(v) for v in c[:3])


def _color_mask(a: np.ndarray, color, tol: int) -> np.ndarray:
    return (np.abs(a[..., :3].astype(np.int16) - np.array(color, np.int16)) <= tol).all(-1) & (a[..., 3] > 0)


FOUR = ndimage.generate_binary_structure(2, 1)


def _peel(a: np.ndarray, tol: int, rounds: int, min_area: int, info: dict):
    """Fonds emboîtés : toute grande zone unie qui touche le vide est elle-même du fond.
    On retire la zone (pas la couleur partout), puis on recommence avec la nouvelle frontière."""
    for _ in range(rounds):
        opaque = a[..., 3] > 0
        frontier = opaque & ndimage.binary_dilation(~opaque, FOUR)
        if not frontier.any():
            break
        fc = a[frontier][:, :3]
        removed_any = False
        for color, n in Counter(map(tuple, fc[:: max(1, len(fc) // 50000)])).most_common(8):
            m = _color_mask(a, color, tol)
            lab, k = ndimage.label(m, FOUR)
            touching = np.unique(lab[frontier & m])
            touching = touching[touching > 0]
            if not len(touching):
                continue
            sizes = np.bincount(lab.ravel(), minlength=k + 1)
            objs = ndimage.find_objects(lab)
            kill = []
            for lb in touching:
                if sizes[lb] < min_area:
                    continue
                sl = objs[lb - 1]
                bh, bw = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
                if bh >= 12 and bw >= 12 and sizes[lb] / (bh * bw) >= 0.3:
                    kill.append(lb)
            if kill:
                a[np.isin(lab, kill), 3] = 0
                info["removed"].append(f"{rgb_to_hex(color)}(zones:{len(kill)})")
                removed_any = True
        if not removed_any:
            break


def border_colors(a: np.ndarray, max_colors=3, cover=0.9, min_share=0.1):
    """Couleur(s) de fond lues sur le bord de l'image. Plusieurs seulement si elles forment
    ensemble presque tout le bord (damier, rayures) : un bord de carte texturé n'en donne qu'une."""
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    border = border[border[:, 3] > 0][:, :3]
    if not len(border):
        return []
    common = Counter(map(tuple, border)).most_common(max_colors)
    out, total = [common[0][0]], common[0][1]
    for color, n in common[1:]:
        if n / len(border) < min_share:
            break
        out.append(color)
        total += n
    if total / len(border) < cover:
        return out[:1]
    return out


def remove_background(im: Image.Image, p: dict):
    """Renvoie (rgba ndarray, infos). Les pixels de fond deviennent alpha=0."""
    a = np.array(im.convert("RGBA"))
    info = {"removed": [], "already_transparent": False}
    if p["bg"] == "none":
        return a, info
    if (a[..., 3] == 0).mean() > 0.01 and p["bg"] == "auto":
        info["already_transparent"] = True
        colors = []
    elif p["bg"] == "auto":
        colors = border_colors(a)
    else:
        bgs = p["bg"] if isinstance(p["bg"], list) else [p["bg"]]
        colors = [hex_to_rgb(c) for c in bgs]
    if p.get("black_bg"):
        colors.append((0, 0, 0))

    # toutes les couleurs de fond ensemble : un damier (2 couleurs) n'est connexe qu'en les réunissant
    if colors:
        m = np.zeros(a.shape[:2], bool)
        for color in colors:
            m |= _color_mask(a, color, p["bg_tol"])
        if p["bg_mode"] == "edge":
            lab, _ = ndimage.label(m)
            edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
            m = np.isin(lab, edge[edge > 0])
        a[m, 3] = 0
        info["removed"] += [rgb_to_hex(c) for c in colors]
    if p.get("peel", 0) > 0:
        _peel(a, p["bg_tol"], p["peel"], p.get("peel_min_area", 256), info)
    a[a[..., 3] == 0] = 0  # pixels transparents propres (évite des RGB parasites)
    return a, info


def components(a: np.ndarray, gap: int):
    """Étiquette les sprites. Deux morceaux séparés par un trou <= gap px sont fusionnés.
    Renvoie (labels sur les pixels opaques uniquement, nombre)."""
    solid = a[..., 3] > 0
    grown = ndimage.binary_dilation(solid, EIGHT, iterations=(gap + 1) // 2) if gap > 0 else solid
    lab, n = ndimage.label(grown, EIGHT)
    lab[~solid] = 0
    return lab, n


def describe(a: np.ndarray, lab: np.ndarray, n: int):
    """Une entrée par composante : bbox, aire, couleurs."""
    items = []
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl is None:
            continue
        mask = lab[sl] == i
        if not mask.any():
            continue
        ys, xs = np.nonzero(mask)
        y0, x0 = sl[0].start + ys.min(), sl[1].start + xs.min()
        y1, x1 = sl[0].start + ys.max() + 1, sl[1].start + xs.max() + 1
        px = a[sl][mask][:, :3]
        cnt = Counter(map(tuple, px))
        items.append({
            "label": i, "x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0),
            "area": int(mask.sum()), "ncolors": len(cnt),
            "dominant": rgb_to_hex(cnt.most_common(1)[0][0]),
            "dom_frac": round(cnt.most_common(1)[0][1] / len(px), 3),
            "kind": "sprite",
        })
    return items


def mark_text(items: list, max_h: int):
    """Repère les légendes : chaînes horizontales de petits glyphes de même couleur dominante,
    alignés sur une même ligne de base et très rapprochés."""
    cand = [it for it in items if it["h"] <= max_h and it["w"] <= 2 * max_h and it["dom_frac"] >= 0.35]
    cand.sort(key=lambda it: (it["y"] + it["h"], it["x"]))
    parent = {id(it): it for it in cand}
    root = {id(it): id(it) for it in cand}

    def find(k):
        while root[k] != k:
            root[k] = root[root[k]]
            k = root[k]
        return k

    by_color = {}
    for it in cand:
        by_color.setdefault(it["dominant"], []).append(it)
    for group in by_color.values():
        group.sort(key=lambda it: it["x"])
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if b["x"] - (a["x"] + a["w"]) > max(2, int(0.45 * max(a["h"], b["h"]))):
                    break
                same_line = abs((a["y"] + a["h"]) - (b["y"] + b["h"])) <= 2 or \
                    min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]) >= 0.6 * min(a["h"], b["h"])
                if same_line and abs(a["h"] - b["h"]) <= max(3, max_h // 3):
                    root[find(id(a))] = find(id(b))
    chains = {}
    for k, it in parent.items():
        chains.setdefault(find(k), []).append(it)
    for members in chains.values():
        if len(members) < 4:
            continue
        # des glyphes ont des formes variées ; une rangée d'objets identiques n'est pas du texte
        shapes = {(it["w"], it["h"], it["area"]) for it in members}
        if len(shapes) >= 0.5 * len(members):
            for it in members:
                it["kind"] = "text"
    # mot déjà soudé en une seule composante : très large, peu haut, peu de couleurs
    for it in items:
        if it["kind"] == "sprite" and it["h"] <= max_h and it["w"] >= 5 * it["h"] and it["dom_frac"] >= 0.55:
            it["kind"] = "text"
    # propagation : un morceau collé à du texte, sur la même ligne et de même couleur, est du texte
    changed = True
    while changed:
        changed = False
        texts = [it for it in items if it["kind"] == "text"]
        for it in items:
            if it["kind"] != "sprite" or it["h"] > max_h:
                continue
            for t in texts:
                if t["dominant"] != it["dominant"]:
                    continue
                gap = max(t["x"] - (it["x"] + it["w"]), it["x"] - (t["x"] + t["w"]))
                overlap = min(t["y"] + t["h"], it["y"] + it["h"]) - max(t["y"], it["y"])
                if gap <= max(2, int(0.45 * t["h"])) and overlap >= 0.5 * min(t["h"], it["h"]):
                    it["kind"] = "text"
                    changed = True
                    break
    return items


def mark_panels(items: list, a: np.ndarray, lab: np.ndarray):
    """Encadrés pleins (crédits, cartouches de titre) : rectangle quasi plein, contour d'une seule couleur."""
    for it in items:
        if it["kind"] != "sprite" or it["w"] < 40 or it["h"] < 14:
            continue
        x, y, w, h = it["x"], it["y"], it["w"], it["h"]
        mask = lab[y:y + h, x:x + w] == it["label"]
        if mask.mean() < 0.93:
            continue
        rgb = a[y:y + h, x:x + w, :3]
        border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
        top = Counter(map(tuple, border)).most_common(1)[0][1] / len(border)
        if top > 0.85:
            it["kind"] = "panel"
    return items


def crop_item(a: np.ndarray, lab: np.ndarray, labels, box) -> np.ndarray:
    """Découpe une boîte en ne gardant que les pixels des labels donnés (pas ceux des voisins)."""
    x, y, w, h = box
    sub = a[y:y + h, x:x + w].copy()
    keep = np.isin(lab[y:y + h, x:x + w], list(labels))
    sub[~keep] = 0
    return sub


GBA_SCREENS = {(240, 160), (480, 320), (720, 480)}


def mark_junk(items: list, a: np.ndarray, lab: np.ndarray, category: str):
    """Déchets typiques des feuilles ripées, marqués kind="junk" (récupérables avec keep) :
    - captures d'écran : rectangle plein de la taille de l'écran GBA (240x160 ou multiple) ;
    - traits : très longs et très fins (séparateurs, soulignements) ;
    - quadrillages / cadres vides : grande boîte presque vide dont les pixels sont sur des lignes pleines."""
    for it in items:
        if it["kind"] != "sprite":
            continue
        w, h = it["w"], it["h"]
        fill = it["area"] / max(1, w * h)
        if category != "ui" and fill >= 0.9 and any(abs(w - sw) <= 2 and abs(h - sh) <= 2 for sw, sh in GBA_SCREENS):
            it["kind"], it["junk"] = "junk", "capture d'écran"
            continue
        if (w >= 32 and h <= 2) or (h >= 32 and w <= 2):
            it["kind"], it["junk"] = "junk", "trait"
            continue
        if w >= 48 and h >= 48 and fill <= 0.12:
            m = lab[it["y"]:it["y"] + h, it["x"]:it["x"] + w] == it["labels"][0][1]
            rows = m.sum(1) >= 0.5 * w
            cols = m.sum(0) >= 0.5 * h
            on_lines = (m & (rows[:, None] | cols[None, :])).sum() / max(1, m.sum())
            if on_lines >= 0.6:
                it["kind"], it["junk"] = "junk", "quadrillage / cadre"
    return items


# ------------------------------------------------------------- retouches au pixel (overrides erase / flood)

def _erase_mask(raw: np.ndarray, e: dict) -> np.ndarray:
    """Pixels visés par une gomme : ceux du rectangle, et seulement des couleurs données s'il y en a."""
    H, W = raw.shape[:2]
    x, y, w, h = e["box"]
    m = np.zeros((H, W), bool)
    m[max(0, y):max(0, min(H, y + h)), max(0, x):max(0, min(W, x + w))] = True
    if e.get("colors"):
        cm = np.zeros((H, W), bool)
        for c in e["colors"]:
            cm |= _color_mask(raw, hex_to_rgb(c), e.get("tol", 0))
        m &= cm
    return m


def _period_fill(a: np.ndarray, m: np.ndarray, px: int, py: int):
    """Bouche les pixels m en recopiant le motif décalé d'une période (fonds en damier / motif répété)."""
    H, W = m.shape
    todo = m.copy()
    for k in range(1, 6):
        for dy, dx in ((0, -px), (0, px), (-py, 0), (py, 0), (-py, -px), (py, px), (-py, px), (py, -px)):
            dy, dx = dy * k, dx * k
            if not todo.any():
                return todo
            ys, xs = np.nonzero(todo)
            sy, sx = ys + dy, xs + dx
            ok = (sy >= 0) & (sy < H) & (sx >= 0) & (sx < W)
            ok[ok] &= ~m[sy[ok], sx[ok]]
            a[ys[ok], xs[ok]] = a[sy[ok], sx[ok]]
            todo[ys[ok], xs[ok]] = False
    return todo


def erase_fill(raw: np.ndarray, erases: list) -> np.ndarray:
    """Gommes avec remplissage (fill = near | LxH), appliquées à l'image SOURCE avant le retrait du fond :
    le texte effacé est remplacé par le fond / motif voisin au lieu de laisser un trou."""
    out = raw.copy()
    for e in erases:
        fill = e.get("fill") or "clear"
        if fill == "clear":
            continue
        m = _erase_mask(raw, e)
        if not m.any():
            continue
        left = m
        if fill != "near":
            px, py = map(int, fill.lower().split("x"))
            left = _period_fill(out, m, px, py)
        if left.any():  # plus proche pixel non effacé
            _, (iy, ix) = ndimage.distance_transform_edt(left, return_indices=True)
            out[left] = out[iy[left], ix[left]]
    return out


def flood_mask(raw: np.ndarray, point, tol: int = 0) -> np.ndarray:
    """Région connexe (4-voisins) de la couleur du point donné, lue sur l'image source."""
    x, y = point
    H, W = raw.shape[:2]
    if not (0 <= x < W and 0 <= y < H):
        return np.zeros((H, W), bool)
    m = (np.abs(raw.astype(np.int16) - raw[y, x].astype(np.int16)) <= tol).all(-1)
    lab, _ = ndimage.label(m, FOUR)
    return lab == lab[y, x]


def post_ops(a: np.ndarray, raw: np.ndarray, ov: dict):
    """Après le retrait du fond : gommes « clear » et remplissages (flood) -> pixels transparents.
    Calculé sur l'image source : appliquer deux fois donne le même résultat."""
    for e in ov.get("erase", []):
        if (e.get("fill") or "clear") == "clear":
            a[_erase_mask(raw, e)] = 0
    for f in ov.get("flood", []):
        a[flood_mask(raw, f["point"], f.get("tol", 0))] = 0
    return a
