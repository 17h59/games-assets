"""Détection de grilles régulières dans les feuilles de sprites (PNJ, ennemis, animations).

Une feuille peut contenir plusieurs blocs, chacun avec sa propre grille. Pour chaque bloc :
- profil d'occupation des colonnes (et des lignes) = nb de pixels opaques ;
- pas = période dominante du profil (autocorrélation), en préférant le plus petit pas quasi aussi bon
  (sinon on trouverait 2 ou 3 fois le vrai pas) ;
- phase = décalage dont les frontières traversent le moins de pixels (milieu du creux) ;
- confiance = 1 - densité sur les frontières / densité moyenne.

Découper par cases règle d'un coup les sprites collés (séparés par la frontière) et les morceaux
détachés (ombre, arme : rattachés à leur case), et aligne parfaitement les frames.
"""
from collections import Counter

import numpy as np
from scipy import ndimage

EIGHT = np.ones((3, 3), bool)


def _period(profile, min_p, max_p):
    """Pas dominant d'un profil 1D. Renvoie (pas, score 0..1) ou (None, 0)."""
    n = len(profile)
    x = profile.astype(float) - profile.mean()
    denom = (x * x).sum()
    if denom == 0 or n < 2 * min_p:
        return None, 0.0
    best = {}
    for lag in range(min_p, min(max_p, n // 2) + 1):
        best[lag] = (x[:-lag] * x[lag:]).sum() / denom * n / (n - lag)
    if not best:
        return None, 0.0
    top_lag = max(best, key=best.get)
    top = best[top_lag]
    if top <= 0:
        return None, 0.0
    # plus petit pas presque aussi bon dont le meilleur pas est un multiple (sinon on prendrait 2x ou 3x le vrai pas)
    for lag in sorted(best):
        k = round(top_lag / lag)
        # un vrai sous-multiple (k >= 2) ; k == 1 voudrait dire « presque le même pas » (31 au lieu de 32)
        if k >= 2 and abs(k * lag - top_lag) <= 1 and best[lag] >= 0.85 * top:
            return lag, float(min(1.0, best[lag]))
    return top_lag, float(min(1.0, top))


def _phase(profile, pitch):
    """Décalage des frontières : milieu de la plus longue suite de décalages de coût minimal."""
    costs = np.array([profile[o::pitch].sum() for o in range(pitch)], float)
    m = costs.min()
    good = costs <= m + 1e-9 + 0.02 * max(1.0, costs.mean())
    # plus longue suite circulaire de "good"
    best_len, best_mid, run = 0, int(np.argmin(costs)), []
    seq = list(range(pitch)) * 2
    for o in seq:
        if good[o]:
            run.append(o)
            if len(run) > best_len and len(run) <= pitch:
                best_len, best_mid = len(run), run[len(run) // 2]
        else:
            run = []
    return best_mid % pitch, costs


def _axis(profile, min_p, max_p):
    pitch, score = _period(profile, min_p, max_p)
    if pitch is None:
        return None
    phase, costs = _phase(profile, pitch)
    mean = profile.mean() if profile.mean() > 0 else 1.0
    boundary = profile[phase::pitch].mean() / mean
    return {"pitch": int(pitch), "phase": int(phase), "score": round(score, 3), "cut": round(float(boundary), 3)}


def blocks(mask, block_gap):
    """Blocs = groupes de sprites séparés par plus de block_gap px de vide."""
    grown = ndimage.binary_dilation(mask, EIGHT, iterations=max(1, block_gap // 2))
    lab, n = ndimage.label(grown, EIGHT)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl is None:
            continue
        sub = mask[sl] & (lab[sl] == i)
        if not sub.any():
            continue
        ys, xs = np.nonzero(sub)
        y0, x0 = sl[0].start + ys.min(), sl[1].start + xs.min()
        y1, x1 = sl[0].start + ys.max() + 1, sl[1].start + xs.max() + 1
        out.append({"id": len(out), "x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0), "label": i})
    return out, lab


def fit_block(mask, b, lab, p):
    """Grille d'un bloc. Renvoie un dict (pas, phase, cases, confiance) ou None si pas de grille."""
    x0, y0, w, h = b["x"], b["y"], b["w"], b["h"]
    sub = mask[y0:y0 + h, x0:x0 + w] & (lab[y0:y0 + h, x0:x0 + w] == b["label"])
    colp, rowp = sub.sum(0), sub.sum(1)
    min_p, max_p = p["grid_min_pitch"], p["grid_max_pitch"]
    if p.get("grid_pitch", "auto") != "auto":
        # pas imposé (zone manuelle) : seule la phase est cherchée, sauf origine imposée aussi
        pw, ph = map(int, str(p["grid_pitch"]).lower().split("x"))
        if p.get("grid_origin", "auto") != "auto":
            gx, gy = map(int, str(p["grid_origin"]).split(","))
            phx, phy = (gx - x0) % pw, (gy - y0) % ph
        else:
            phx, phy = _phase(colp, pw)[0], _phase(rowp, ph)[0]
        mean_c, mean_r = max(colp.mean(), 1e-9), max(rowp.mean(), 1e-9)
        cx_, cy_ = colp[phx::pw], rowp[phy::ph]
        ax = {"pitch": pw, "phase": int(phx), "score": 1.0, "cut": round(float(cx_.mean() / mean_c), 3) if len(cx_) else 0.0}
        ay = {"pitch": ph, "phase": int(phy), "score": 1.0, "cut": round(float(cy_.mean() / mean_r), 3) if len(cy_) else 0.0}
    else:
        ax = _axis(colp, min_p, max_p)
        ay = _axis(rowp, min_p, max_p)
    # une seule colonne / une seule ligne de cases : l'axe vaut tout le bloc
    if ax is None and w <= max_p:
        ax = {"pitch": w + 2, "phase": 0, "score": 1.0, "cut": 0.0, "single": True}
    if ay is None and h <= max_p:
        ay = {"pitch": h + 2, "phase": 0, "score": 1.0, "cut": 0.0, "single": True}
    if ax is None or ay is None:
        return None
    if ax.get("single") and ay.get("single"):
        return None  # un seul sprite : rien à gagner
    conf = 1.0 - max(ax["cut"], ay["cut"])
    score = min(ax["score"], ay["score"])
    forced = p.get("grid_pitch", "auto") != "auto"
    if not forced and (conf < p["grid_min_conf"] or score < 0.3):
        return {"ok": False, "ax": ax, "ay": ay, "conf": round(conf, 3), "score": round(score, 3)}
    # bornes des cases (les frontières tombent sur les colonnes de phase)
    def bounds(n, a):
        if a.get("single"):
            return [(0, n)]
        pitch = a["pitch"]
        start = a["phase"] % pitch
        if start > 0:
            start -= pitch  # première frontière à gauche (ou en haut) du bloc
        edges = list(range(start, n + pitch, pitch))
        return [(max(0, s), min(n, e)) for s, e in zip(edges[:-1], edges[1:]) if min(n, e) > max(0, s)]
    return {"ok": True, "ax": ax, "ay": ay, "conf": round(conf, 3), "score": round(score, 3),
            "cols": bounds(w, ax), "rows": bounds(h, ay)}


def apply(a, items, p, mask):
    """Remplace, bloc par bloc, les taches par des cases quand une grille fiable est trouvée.

    Renvoie (items, lab_cells, rapport). Les items d'une case ont labels [("c", id)] et des champs
    cell=[x,y,w,h], block, row, col. Les taches hors grille sont gardées telles quelles."""
    keep = [it for it in items if it["kind"] == "sprite"]
    lab_cells = np.zeros(a.shape[:2], np.int32)
    if not keep:
        return items, lab_cells, []
    # mask = pixels des sprites gardés seulement (texte et encarts jetés n'influencent pas la grille)
    blks, blab = blocks(mask, p["block_gap"])
    report, new_items, consumed = [], [], set()
    next_id = 1
    for b in blks:
        fit = fit_block(mask, b, blab, p)
        inside = [it for it in keep if b["x"] <= it["x"] + it["w"] / 2 < b["x"] + b["w"]
                  and b["y"] <= it["y"] + it["h"] / 2 < b["y"] + b["h"]]
        entry = {"block": b["id"], "box": [b["x"], b["y"], b["w"], b["h"]], "sprites": len(inside)}
        if fit:
            entry.update({k: fit[k] for k in ("conf", "score")})
            entry["pitch"] = [fit["ax"]["pitch"], fit["ay"]["pitch"]]
        rects = None
        forced = p.get("grid_pitch", "auto") != "auto"  # pas imposé : on découpe même un seul bloc soudé
        if fit and fit["ok"] and (forced or len(inside) >= p["grid_min_sprites"]):
            entry["mode"] = "grille"
            entry["forced"] = forced
            rects = [(ri, ci, ys, ye, xs, xe) for ri, (ys, ye) in enumerate(fit["rows"])
                     for ci, (xs, xe) in enumerate(fit["cols"])]
        elif len(inside) >= p["grid_min_sprites"]:
            xy = fit_xycut(mask, b, blab, p)
            if xy and xy["ok"]:
                entry.update({"mode": "xycut", "conf": xy["conf"], "splits": xy["splits"],
                              "fragments": xy["merged"], "pitch": xy["ref"]})
                # boîtes absolues -> rectangles relatifs au bloc ; pas d'indices de case (row/col = None)
                rects = [(None, None, by - b["y"], by - b["y"] + bh, bx - b["x"], bx - b["x"] + bw)
                         for bx, by, bw, bh in xy["boxes"]]
            elif xy:
                entry.update({"xycut_conf": xy["conf"]})
        if rects is None:
            entry["mode"] = "taches"
            report.append(entry)
            continue
        bm = mask[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]] & (blab[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]] == b["label"])
        cells = 0
        for ri, ci, ys, ye, xs, xe in rects:
            if True:
                cm = bm[ys:ye, xs:xe]
                if cm.sum() < p["min_area"]:
                    continue
                yy, xx = np.nonzero(cm)
                gx0, gy0 = b["x"] + xs, b["y"] + ys
                tx0, ty0 = gx0 + int(xx.min()), gy0 + int(yy.min())
                tx1, ty1 = gx0 + int(xx.max()) + 1, gy0 + int(yy.max()) + 1
                region = lab_cells[gy0:gy0 + (ye - ys), gx0:gx0 + (xe - xs)]
                region[cm] = next_id
                px = a[gy0:gy0 + (ye - ys), gx0:gx0 + (xe - xs)][cm][:, :3]
                cnt = Counter(map(tuple, px))
                top, topn = cnt.most_common(1)[0]
                it = {"x": tx0, "y": ty0, "w": tx1 - tx0, "h": ty1 - ty0, "labels": [("c", next_id)],
                      "area": int(cm.sum()), "ncolors": len(cnt), "dominant": "#%02X%02X%02X" % tuple(int(v) for v in top),
                      "dom_frac": round(topn / len(px), 3), "kind": "sprite"}
                if ri is not None:  # vraie grille : case fixe, indices de rangée / colonne
                    it.update({"cell": [gx0, gy0, xe - xs, ye - ys], "block": b["id"], "row": ri, "col": ci})
                new_items.append(it)
                next_id += 1
                cells += 1
        entry["cells"] = cells
        consumed.update(id(it) for it in inside)
        report.append(entry)
    out = [it for it in items if id(it) not in consumed] + new_items
    return out, lab_cells, report


# --------------------------------------------------------------------------- grille souple (gouttières)

def _runs(profile, min_gap=1):
    """Suites d'indices où profile > 0, séparées par >= min_gap zéros. Renvoie [(début, fin)]."""
    runs, start, zeros = [], None, 0
    for i, v in enumerate(profile):
        if v > 0:
            if start is None:
                start = i
            zeros = 0
            end = i + 1
        elif start is not None:
            zeros += 1
            if zeros >= min_gap:
                runs.append((start, end)); start = None
    if start is not None:
        runs.append((start, end))
    return runs


def _split_wide(runs, profile, ref):
    """Coupe les suites trop larges (sprites collés) au point le moins dense près des multiples de ref."""
    out, splits = [], 0
    for s, e in runs:
        n = round((e - s) / ref)
        if (e - s) >= 1.6 * ref and n >= 2:
            cuts = []
            for k in range(1, n):
                target = s + k * (e - s) / n
                lo, hi = int(target - ref * 0.3), int(target + ref * 0.3) + 1
                lo, hi = max(lo, s + 1), min(hi, e - 1)
                if hi <= lo:
                    continue
                cuts.append(lo + int(np.argmin(profile[lo:hi])))
            edges = [s] + cuts + [e]
            out += [(a, b) for a, b in zip(edges[:-1], edges[1:]) if b > a]
            splits += len(cuts)
        else:
            out.append((s, e))
    return out, splits


def _absorb_small(runs, ref, frac=0.45):
    """Rattache les suites trop petites (ombre, pointe d'arme) à la voisine la plus proche."""
    runs = list(runs)
    changed = True
    while changed and len(runs) > 1:
        changed = False
        for i, (s, e) in enumerate(runs):
            if e - s < frac * ref:
                left = runs[i - 1] if i > 0 else None
                right = runs[i + 1] if i + 1 < len(runs) else None
                gl = s - left[1] if left else 1e9
                gr = right[0] - e if right else 1e9
                if gl <= gr and left:
                    runs[i - 1] = (left[0], e); del runs[i]
                elif right:
                    runs[i + 1] = (s, right[1]); del runs[i]
                changed = True
                break
    return runs


def _xycut(sub, x, y, w, h, out, depth=0):
    """Découpage XY récursif : coupe sur les lignes / colonnes entièrement vides de la région."""
    region = sub[y:y + h, x:x + w]
    if not region.any():
        return
    for axis in (0, 1):  # 0 : rangées (coupes horizontales), 1 : colonnes
        prof = region.sum(1 - axis)
        runs = _runs(prof)
        if len(runs) > 1 and depth < 60:
            for s_, e_ in runs:
                if axis == 0:
                    _xycut(sub, x, y + s_, w, e_ - s_, out, depth + 1)
                else:
                    _xycut(sub, x + s_, y, e_ - s_, h, out, depth + 1)
            return
    ys, xs = np.nonzero(region)
    out.append([x + int(xs.min()), y + int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)])


def _gap(a, b):
    dx = max(b[0] - (a[0] + a[2]), a[0] - (b[0] + b[2]), 0)
    dy = max(b[1] - (a[1] + a[3]), a[1] - (b[1] + b[3]), 0)
    return max(dx, dy)


def fit_xycut(mask, b, lab, p):
    """Feuilles régulières mais assemblées à la main (pas qui dérive, sous-grilles décalées) :
    XY-cut récursif, puis séparation des sprites collés (trop larges / trop hauts par rapport à la
    taille typique) et rattachement des fragments (ombre, pointe d'arme) au sprite voisin."""
    x0, y0, w, h = b["x"], b["y"], b["w"], b["h"]
    sub = mask[y0:y0 + h, x0:x0 + w] & (lab[y0:y0 + h, x0:x0 + w] == b["label"])
    leaves = []
    _xycut(sub, 0, 0, w, h, leaves)
    if len(leaves) < p["grid_min_sprites"]:
        return None
    big = [l for l in leaves if l[2] >= 4 and l[3] >= 4]
    ref_w = float(np.median([l[2] for l in big] or [8]))
    ref_h = float(np.median([l[3] for l in big] or [8]))
    splits = 0
    # sprites collés : feuille trop large -> coupe au point le moins dense près des multiples de ref_w
    out = []
    for l in leaves:
        lx, ly, lw, lh = l
        if lw >= 1.6 * ref_w and lh <= 1.5 * ref_h:
            prof = sub[ly:ly + lh, lx:lx + lw].sum(0)
            pieces, k = _split_wide([(0, lw)], prof, ref_w)
            splits += k
            for s_, e_ in pieces:
                reg = sub[ly:ly + lh, lx + s_:lx + e_]
                if reg.any():
                    yy, xx = np.nonzero(reg)
                    out.append([lx + s_ + int(xx.min()), ly + int(yy.min()), int(xx.max() - xx.min() + 1), int(yy.max() - yy.min() + 1)])
        elif lh >= 1.6 * ref_h and lw <= 1.5 * ref_w:
            prof = sub[ly:ly + lh, lx:lx + lw].sum(1)
            pieces, k = _split_wide([(0, lh)], prof, ref_h)
            splits += k
            for s_, e_ in pieces:
                reg = sub[ly + s_:ly + e_, lx:lx + lw]
                if reg.any():
                    yy, xx = np.nonzero(reg)
                    out.append([lx + int(xx.min()), ly + s_ + int(yy.min()), int(xx.max() - xx.min() + 1), int(yy.max() - yy.min() + 1)])
        else:
            out.append(list(l))
    # fragments : petit (< 45 % de la taille typique sur les deux axes) et collé (<= 3 px) à un voisin
    merged = 0
    changed = True
    while changed:
        changed = False
        for i, l in enumerate(out):
            if l[2] < 0.45 * ref_w and l[3] < 0.45 * ref_h:
                cands = [(j, _gap(l, o)) for j, o in enumerate(out) if j != i]
                if not cands:
                    break
                j, g = min(cands, key=lambda c: c[1])
                if g <= p["frag_gap"]:
                    o = out[j]
                    nx0, ny0 = min(o[0], l[0]), min(o[1], l[1])
                    nx1, ny1 = max(o[0] + o[2], l[0] + l[2]), max(o[1] + o[3], l[1] + l[3])
                    out[j] = [nx0, ny0, nx1 - nx0, ny1 - ny0]
                    del out[i]
                    merged += 1
                    changed = True
                    break
    ws = [o[2] for o in out if o[2] >= 4]
    hs = [o[3] for o in out if o[3] >= 4]
    cv = max(float(np.std(ws) / max(1, np.mean(ws))), float(np.std(hs) / max(1, np.mean(hs))))
    conf = max(0.0, 1.0 - cv * 2)
    return {"ok": conf >= 0.5, "conf": round(conf, 3), "splits": splits, "merged": merged,
            "ref": [round(ref_w, 1), round(ref_h, 1)],
            "boxes": [[x0 + o[0], y0 + o[1], o[2], o[3]] for o in out]}
