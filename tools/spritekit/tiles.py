"""Cartes et tilesets : zones -> grille -> tuiles uniques -> bibliothèque par jeu.

Une feuille de carte contient une ou plusieurs zones (cartes, morceaux de décor) entourées de fond.
Pour chaque zone on cherche le décalage de grille (ox, oy) qui minimise le nombre de tuiles uniques :
les vraies tuiles d'un jeu se répètent énormément, un mauvais décalage casse ces répétitions.
"""
import hashlib
import json
import os

import numpy as np
from PIL import Image

from . import config, imageops

# cartes : on ne retire que le fond relié au bord, sans tolérance (le sol peut avoir une couleur proche),
# puis on épluche les cartouches/cadres unis de grande taille (zone >= 1024 px)
TILE_PARAMS = {"bg_mode": "edge", "bg_tol": 0, "peel": 3, "peel_min_area": 1024}


def tile_params(cfg):
    p = config.params(cfg)
    for k, v in TILE_PARAMS.items():
        if k not in cfg.get("params", {}):
            p[k] = v
    return p


def load(cfg):
    """Image de la carte sans fond ; les retouches `erase` / `flood` de la fiche (crédits, portraits collés
    à la carte) s'appliquent aussi : les pixels effacés ne comptent plus dans la reconstruction."""
    p = tile_params(cfg)
    raw = Image.open(os.path.join(config.PROJECT, cfg["src"])).convert("RGBA")
    ov = cfg.get("overrides", {})
    raw_arr = np.array(raw)
    if any((e.get("fill") or "clear") != "clear" for e in ov.get("erase", [])):
        raw = Image.fromarray(imageops.erase_fill(raw_arr, ov["erase"]))
    a, info = imageops.remove_background(raw, p)
    imageops.post_ops(a, raw_arr, ov)
    return a, info, p


def find_regions(a, t, min_tiles=1):
    """Zones opaques assez grandes pour contenir au moins `min_tiles` tuiles entières."""
    lab, n = imageops.components(a, 2)
    regions = []
    for i, it in enumerate(imageops.describe(a, lab, n)):
        if it["w"] >= t and it["h"] >= t and it["area"] >= min_tiles * t * t:
            regions.append({"x": it["x"], "y": it["y"], "w": it["w"], "h": it["h"], "area": it["area"],
                            "dom_frac": it["dom_frac"]})
    regions.sort(key=lambda r: (r["y"], r["x"]))
    return regions


def _blocks(a, x, y, w, h, t, ox, oy, nx=None, ny=None):
    """Tuiles entières de la zone pour un décalage donné : (tableau N x t*t*4, ny, nx, origine).
    nx/ny imposés : même nombre de tuiles pour tous les décalages (comparaison équitable)."""
    x0, y0 = x + ox, y + oy
    nx = (w - ox) // t if nx is None else nx
    ny = (h - oy) // t if ny is None else ny
    if nx <= 0 or ny <= 0:
        return None, 0, 0, (x0, y0)
    sub = a[y0:y0 + ny * t, x0:x0 + nx * t]
    blocks = sub.reshape(ny, t, nx, t, 4).transpose(0, 2, 1, 3, 4).reshape(ny * nx, t * t * 4)
    return blocks, ny, nx, (x0, y0)


def _score(blocks, t):
    alpha = blocks.reshape(len(blocks), t * t, 4)[:, :, 3] > 0
    frac = alpha.mean(1)
    nonempty = frac > 0
    if not nonempty.any():
        return None
    b = blocks[nonempty]
    uniq = len(np.unique(b.view(np.dtype((np.void, b.shape[1])))))
    partial = int(((frac > 0) & (frac < 1)).sum())
    return uniq / nonempty.sum(), partial, int(nonempty.sum()), uniq


def detect_offset(a, r, t):
    """Meilleur décalage de grille pour une zone. Renvoie (ox, oy, stats, confiance 0..1)."""
    # on ne teste que sur un morceau central si la zone est énorme (rapide, même résultat)
    x, y, w, h = r["x"], r["y"], r["w"], r["h"]
    if w * h > 600 * 600:
        cw, ch = min(w, 600), min(h, 600)
        x, y, w, h = x + (w - cw) // 2 // t * t, y + (h - ch) // 2 // t * t, cw, ch
    # même nombre de tuiles pour chaque décalage, sinon perdre une rangée de bord (souvent unique)
    # améliore artificiellement le ratio
    nxm, nym = (w - t + 1) // t, (h - t + 1) // t
    fixed = nxm >= 1 and nym >= 1
    scores, coverage = {}, {}
    for oy in range(t):
        for ox in range(t):
            blocks, ny, nx, _ = _blocks(a, x, y, w, h, t, ox, oy, *((nxm, nym) if fixed else (None, None)))
            if blocks is None:
                continue
            s = _score(blocks, t)
            if s:
                scores[(ox, oy)] = s
                coverage[(ox, oy)] = ((w - ox) // t) * ((h - oy) // t)
    if not scores:
        return 0, 0, None, 0.0
    best = min(scores, key=lambda k: (round(scores[k][0], 3), scores[k][1], -coverage[k]))
    ratios = sorted(s[0] for s in scores.values())
    med = ratios[len(ratios) // 2]
    conf = 0.0 if med == 0 else max(0.0, min(1.0, (med - scores[best][0]) / med))
    # la grille est relative au coin de la zone source : on la ramène à la zone complète
    ox = (x + best[0] - r["x"]) % t
    oy = (y + best[1] - r["y"]) % t
    return ox, oy, scores[best], conf


def tile_hash(block: np.ndarray) -> str:
    return hashlib.blake2b(block.tobytes(), digest_size=8).hexdigest()


REF_TRUST = 0.5   # au-dessus, la grille trouvée par unicité est jugée sûre


def analyze(cfg, use_reference=True):
    """Zones + grille de chaque zone (sans écrire). Les réglages par zone viennent de cfg['regions'].
    Les zones peu sûres sont recalées sur la référence du jeu (tuiles vues dans des zones sûres)."""
    a, info, p = load(cfg)
    t = int(p["tile"])
    min_tiles = 1 if cfg["type"] == "tileset" else 4
    regions = find_regions(a, t, min_tiles)
    manual = cfg.get("regions", {})
    for i, r in enumerate(regions):
        r["id"] = i
        key = next((k for k in manual if _contains(r, *map(int, k.split(",")))), None)
        r["manual"] = manual.get(key, {}) if key else {}
        if r["manual"].get("skip"):
            r["skip"] = True
            continue
        if "offset" in r["manual"]:
            r["ox"], r["oy"] = r["manual"]["offset"]
            r["conf"], r["stats"] = 1.0, None
        elif p["grid_offset"] != "auto":
            gx, gy = map(int, str(p["grid_offset"]).split(","))
            r["ox"], r["oy"] = (gx - r["x"]) % t, (gy - r["y"]) % t
            r["conf"], r["stats"] = 1.0, None
        else:
            r["ox"], r["oy"], r["stats"], r["conf"] = detect_offset(a, r, t)
            r["method"] = "unicité"
            if r["stats"] and r["stats"][3] <= 1 and not r["manual"].get("unskip"):
                r["skip"], r["auto_skip"] = True, "zone unie (fond ou cadre)"
                continue
            if use_reference and r["conf"] < REF_TRUST:
                ref = reference(cfg["game"])
                if ref:
                    hit = offset_by_reference(a, r, t, ref)
                    if hit:
                        r["ox"], r["oy"], r["conf"] = hit
                        r["method"] = "référence"
        blocks, ny, nx, origin = _blocks(a, r["x"], r["y"], r["w"], r["h"], t, r["ox"], r["oy"])
        r["cols"], r["rows"], r["origin"] = nx, ny, list(origin)
    return a, regions, info, p


_REF_CACHE = {}


def reference(game, rebuild=False, rounds=5):
    """Ensemble des tuiles (hash) dignes de confiance pour un jeu, construit par bootstrap :
    1) graine = tuiles vues >= 2 fois dans les zones dont la grille est sûre par unicité ;
    2) chaque zone douteuse qui se recale nettement sur la référence y ajoute ses tuiles ; on recommence.
    Mis en cache dans rpg/assets/<jeu>/tiles/reference.json."""
    if game in _REF_CACHE and not rebuild:
        return _REF_CACHE[game]
    path = os.path.join(config.ASSETS, game, "tiles", "reference.json")
    if os.path.exists(path) and not rebuild:
        with open(path) as f:
            _REF_CACHE[game] = set(json.load(f))
        return _REF_CACHE[game]
    counts, pending = {}, []
    for cfg in config.all_sheets():
        if cfg["game"] != game or cfg["type"] != "map" or cfg["status"] == "skip":
            continue
        a, regions, _, p = analyze(cfg, use_reference=False)
        t = int(p["tile"])
        for r in regions:
            if r.get("skip") or not r.get("stats"):
                continue
            if r["conf"] >= REF_TRUST and r["stats"][2] >= 60:
                for _, _, h, _ in region_tiles(a, r, t, opaque_only=True):
                    counts[h] = counts.get(h, 0) + 1
            elif "offset" not in r["manual"]:
                # on garde seulement le morceau utile de l'image pour les passes suivantes
                crop = a[r["y"]:r["y"] + r["h"], r["x"]:r["x"] + r["w"]].copy()
                pending.append((crop, dict(r, x=0, y=0), t))
    ref = {h for h, n in counts.items() if n >= 2}
    for _ in range(rounds):
        still, added = [], 0
        for crop, r, t in pending:
            hit = offset_by_reference(crop, r, t, ref)
            if hit and hit[2] >= REF_TRUST:
                rr = dict(r, ox=hit[0], oy=hit[1])
                for _, _, h, _ in region_tiles(crop, rr, t, opaque_only=True):
                    if h not in ref:
                        ref.add(h); added += 1
            else:
                still.append((crop, r, t))
        pending = still
        if not added:
            break
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(sorted(ref), f)
    _REF_CACHE[game] = ref
    return ref


def _ref_hits(a, r, t, ref):
    """Pour chaque décalage : ensemble des tuiles connues retrouvées."""
    nxm, nym = (r["w"] - t + 1) // t, (r["h"] - t + 1) // t
    if nxm < 1 or nym < 1:
        return {}
    out = {}
    for oy in range(t):
        for ox in range(t):
            blocks, _, _, _ = _blocks(a, r["x"], r["y"], r["w"], r["h"], t, ox, oy, nxm, nym)
            if blocks is None:
                continue
            opaque = (blocks.reshape(len(blocks), -1, 4)[:, :, 3] > 0).all(1)
            out[(ox, oy)] = {h for h in (tile_hash(b) for b in blocks[opaque]) if h in ref}
    return out


def offset_by_reference(a, r, t, ref):
    """Décalage qui retrouve des tuiles connues. Une tuile identique au pixel près ne coïncide
    pratiquement jamais par hasard. Les tuiles retrouvées à plusieurs décalages (motifs périodiques :
    parquet, herbe) ne prouvent rien : on ne compte que celles propres à un seul décalage.
    Renvoie (ox, oy, confiance) ou None."""
    hits = _ref_hits(a, r, t, ref)
    if not hits:
        return None
    seen = {}
    for s_ in hits.values():
        for h in s_:
            seen[h] = seen.get(h, 0) + 1
    informative = sorted(((sum(1 for h in s_ if seen[h] == 1), k) for k, s_ in hits.items()), reverse=True)
    best, second = informative[0][0], (informative[1][0] if len(informative) > 1 else 0)
    if best >= 1 and second == 0:
        conf = min(1.0, 0.5 + 0.1 * best)
    elif best >= 3 * second + 2:
        conf = 0.5
    else:
        return None
    ox, oy = informative[0][1]
    return ox, oy, round(conf, 2)


def _contains(r, x, y):
    return r["x"] <= x < r["x"] + r["w"] and r["y"] <= y < r["y"] + r["h"]


def region_tiles(a, r, t, opaque_only=False):
    """Liste (row, col, hash, block) des tuiles non vides d'une zone.
    opaque_only : ne garde que les tuiles sans aucun pixel transparent (cartes : le reste est du parasite)."""
    blocks, ny, nx, _ = _blocks(a, r["x"], r["y"], r["w"], r["h"], t, r["ox"], r["oy"])
    out = []
    if blocks is None:
        return out
    for k in range(len(blocks)):
        b = blocks[k]
        alpha = b.reshape(-1, 4)[:, 3]
        if not (alpha > 0).any() or (opaque_only and (alpha == 0).any()):
            continue
        out.append((k // nx, k % nx, tile_hash(b), b))
    return out


# --------------------------------------------------------------------------- bibliothèque par jeu

def build_library(game, page_cols=64, page_rows=64):
    """Rassemble toutes les tuiles uniques des cartes/tilesets d'un jeu (statut != skip).

    Écrit rpg/assets/<jeu>/tiles/ : atlas_N.png, library.json (tuile -> position, nb d'occurrences,
    feuilles d'origine, voisinages) et une matrice par zone dans maps/<feuille>/region_N.json."""
    out = os.path.join(config.ASSETS, game, "tiles")
    maps_out = os.path.join(config.ASSETS, game, "maps")
    import shutil
    shutil.rmtree(maps_out, ignore_errors=True)  # les indices de tuiles changent à chaque reconstruction
    os.makedirs(out, exist_ok=True)
    lib, order, adjacency = {}, [], {}
    tile_size = None
    sheets = [c for c in config.all_sheets() if c["game"] == game and c["type"] in ("map", "tileset")
              and c["status"] != "skip"]
    for cfg in sheets:
        a, regions, info, p = analyze(cfg)
        t = int(p["tile"])
        if tile_size is None:
            tile_size = t
        elif t != tile_size:
            print(f"  ! {cfg['id']} : tuile {t} != {tile_size}, ignorée"); continue
        sheet_dir = os.path.join(maps_out, config.slug(cfg["title"]) + f"_{cfg['id']}")
        os.makedirs(sheet_dir, exist_ok=True)
        covered = total = 0
        for r in regions:
            if r.get("skip"):
                continue
            grid = [[-1] * r["cols"] for _ in range(r["rows"])]
            for row, col, h, b in region_tiles(a, r, t, opaque_only=cfg["type"] == "map"):
                if h not in lib:
                    lib[h] = {"i": len(order), "count": 0, "sheets": set(), "partial": bool((b.reshape(-1, 4)[:, 3] == 0).any())}
                    order.append(b)
                e = lib[h]
                e["count"] += 1
                e["sheets"].add(cfg["id"])
                grid[row][col] = e["i"]
            for row in range(r["rows"]):
                for col in range(r["cols"]):
                    cur = grid[row][col]
                    if cur < 0:
                        continue
                    if col + 1 < r["cols"] and grid[row][col + 1] >= 0:
                        k = f"{cur}>{grid[row][col + 1]}"; adjacency[k] = adjacency.get(k, 0) + 1
                    if row + 1 < r["rows"] and grid[row + 1][col] >= 0:
                        k = f"{cur}v{grid[row + 1][col]}"; adjacency[k] = adjacency.get(k, 0) + 1
            # aperçu reconstruit à partir des tuiles + part des pixels de la zone reproduits
            prev = np.zeros((r["rows"] * t, r["cols"] * t, 4), np.uint8)
            for row in range(r["rows"]):
                for col in range(r["cols"]):
                    if grid[row][col] >= 0:
                        prev[row * t:(row + 1) * t, col * t:(col + 1) * t] = order[grid[row][col]].reshape(t, t, 4)
            ox, oy = r["origin"]
            src = a[oy:oy + r["rows"] * t, ox:ox + r["cols"] * t]
            src_op = src[..., 3] > 0
            same = (prev == src).all(-1) & src_op
            covered += int(same.sum()); total += int(src_op.sum())
            Image.fromarray(prev).save(os.path.join(sheet_dir, f"region_{r['id']}.png"))
            with open(os.path.join(sheet_dir, f"region_{r['id']}.json"), "w") as f:
                json.dump({"sheet": cfg["id"], "title": cfg["title"], "region": r["id"], "tile": t,
                           "origin": r["origin"], "cols": r["cols"], "rows": r["rows"], "grid": grid,
                           "coverage": round(float(same.sum()) / max(1, int(src_op.sum())), 4)}, f)
        # confirmations automatiques (signées « outil ») : rien de perdu ; grille sûre partout
        from . import checks
        cov = covered / max(1, total)
        live = config.load(cfg["id"])
        if cov >= 0.97:
            checks.confirm(live, "reconstruction", "ok", f"{cov:.1%} des pixels des zones reproduits par les tuiles",
                           by="outil")
        live_regions = [r for r in regions if not r.get("skip")]
        if live_regions and all(r.get("conf", 0) >= REF_TRUST for r in live_regions):
            checks.confirm(live, "grille", "ok", f"{len(live_regions)} zone(s), toutes de confiance >= {REF_TRUST}",
                           by="outil")
        config.save(live)
    # atlas paginés
    per_page = page_cols * page_rows
    t = tile_size or 16
    for f in os.listdir(out):
        if f.startswith("atlas_"):
            os.remove(os.path.join(out, f))
    for pg in range(0, len(order), per_page):
        chunk = order[pg:pg + per_page]
        rows = (len(chunk) + page_cols - 1) // page_cols
        atlas = np.zeros((rows * t, page_cols * t, 4), np.uint8)
        for k, b in enumerate(chunk):
            r_, c_ = divmod(k, page_cols)
            atlas[r_ * t:(r_ + 1) * t, c_ * t:(c_ + 1) * t] = b.reshape(t, t, 4)
        Image.fromarray(atlas).save(os.path.join(out, f"atlas_{pg // per_page}.png"))
    tiles = [None] * len(order)
    for h, e in lib.items():
        pg, k = divmod(e["i"], per_page)
        tiles[e["i"]] = {"hash": h, "page": pg, "col": k % page_cols, "row": k // page_cols,
                         "count": e["count"], "partial": e["partial"], "sheets": sorted(e["sheets"])}
    with open(os.path.join(out, "library.json"), "w") as f:
        json.dump({"game": game, "tile": t, "page_cols": page_cols, "page_rows": page_rows,
                   "tiles": tiles}, f)
    with open(os.path.join(out, "adjacency.json"), "w") as f:
        json.dump(adjacency, f)
    return len(order), len(sheets)


# --------------------------------------------------------------------------- contrôle visuel

def render(cfg, a, regions, p, region_only=None, scale=None):
    """Planche : feuille avec zones (cadre) et grille détectée (lignes fines), numéros zN."""
    from PIL import ImageDraw
    from .qa import _checker, _font, MAX_PAGE
    t = int(p["tile"])
    h, w = a.shape[:2]
    x0, y0, x1, y1 = (0, 0, w, h)
    if region_only is not None:
        r = regions[region_only]
        x0, y0, x1, y1 = r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]
    if scale is None:
        scale = 2 if max(x1 - x0, y1 - y0) <= 900 else 1
    img = _checker((x1 - x0) * scale, (y1 - y0) * scale)
    img.alpha_composite(Image.fromarray(a[y0:y1, x0:x1]).resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST))
    d = ImageDraw.Draw(img)
    font = _font(12)
    for r in regions:
        if region_only is not None and r["id"] != region_only:
            continue
        X, Y = (r["x"] - x0) * scale, (r["y"] - y0) * scale
        color = (150, 150, 150) if r.get("skip") else (0, 220, 0) if r["conf"] >= 0.3 else (255, 160, 0)
        if not r.get("skip"):
            gx0, gy0 = r["origin"]
            for c in range(r["cols"] + 1):
                xx = (gx0 + c * t - x0) * scale
                d.line([(xx, (gy0 - y0) * scale), (xx, (gy0 + r["rows"] * t - y0) * scale)], fill=(255, 0, 255, 120))
            for rr in range(r["rows"] + 1):
                yy = (gy0 + rr * t - y0) * scale
                d.line([((gx0 - x0) * scale, yy), ((gx0 + r["cols"] * t - x0) * scale, yy)], fill=(255, 0, 255, 120))
        d.rectangle([X - 2, Y - 2, X + r["w"] * scale + 1, Y + r["h"] * scale + 1], outline=color, width=2)
        label = f"z{r['id']}" + ("" if r.get("skip") else f" off={r['ox']},{r['oy']} conf={r['conf']:.2f}")
        tw = d.textlength(label, font=font)
        d.rectangle([X, Y, X + tw + 4, Y + 14], fill=(0, 0, 0))
        d.text((X + 2, Y), label, fill=color, font=font)
    out_dir = os.path.join(config.QA_DIR, cfg["id"])
    os.makedirs(out_dir, exist_ok=True)
    stem = "regions" if region_only is None else f"region_{region_only}"
    for f in os.listdir(out_dir):
        if f.startswith(stem + "_") and f.endswith(".png"):
            os.remove(os.path.join(out_dir, f))
    paths = []
    W, H = img.size
    for py in range(0, H, MAX_PAGE):
        for px in range(0, W, MAX_PAGE):
            path = os.path.join(out_dir, f"{stem}_{py // MAX_PAGE}_{px // MAX_PAGE}.png")
            img.crop((px, py, min(W, px + MAX_PAGE), min(H, py + MAX_PAGE))).save(path)
            paths.append(path)
    return paths


def candidates(a, r, t, ref=None, k=4):
    """Les k meilleurs décalages d'une zone (unicité, puis correspondances avec la référence)."""
    nxm, nym = (r["w"] - t + 1) // t, (r["h"] - t + 1) // t
    fixed = (nxm, nym) if nxm >= 1 and nym >= 1 else (None, None)
    rows = []
    for oy in range(t):
        for ox in range(t):
            blocks, _, _, _ = _blocks(a, r["x"], r["y"], r["w"], r["h"], t, ox, oy, *fixed)
            if blocks is None:
                continue
            sc = _score(blocks, t)
            if not sc:
                continue
            hits = 0
            if ref:
                opaque = (blocks.reshape(len(blocks), -1, 4)[:, :, 3] > 0).all(1)
                hits = sum(tile_hash(b) in ref for b in blocks[opaque])
            rows.append({"ox": ox, "oy": oy, "ratio": round(sc[0], 3), "uniq": sc[3], "tiles": sc[2], "ref_hits": hits})
    rows.sort(key=lambda c: (-c["ref_hits"], c["ratio"]))
    return rows[:k]


def render_candidates(cfg, a, r, t, cands, scale=3):
    """Une vignette par décalage candidat (A, B, C, D), grille dessinée, côte à côte."""
    from PIL import ImageDraw
    from .qa import _checker, _font
    font = _font(14)
    crop = a[r["y"]:r["y"] + r["h"], r["x"]:r["x"] + r["w"]]
    W, H = r["w"] * scale, r["h"] * scale
    max_w = 1400
    cols = max(1, min(len(cands), max_w // (W + 10)))
    rows_n = (len(cands) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * (W + 10) + 10, rows_n * (H + 30) + 10), (40, 40, 48, 255))
    d = ImageDraw.Draw(sheet)
    for i, c in enumerate(cands):
        X, Y = 10 + (i % cols) * (W + 10), 10 + (i // cols) * (H + 30)
        img = _checker(W, H)
        img.alpha_composite(Image.fromarray(crop).resize((W, H), Image.NEAREST))
        dd = ImageDraw.Draw(img)
        for gx in range(c["ox"], r["w"] + 1, t):
            dd.line([(gx * scale, 0), (gx * scale, H)], fill=(255, 0, 255, 200))
        for gy in range(c["oy"], r["h"] + 1, t):
            dd.line([(0, gy * scale), (W, gy * scale)], fill=(255, 0, 255, 200))
        sheet.alpha_composite(img, (X, Y + 20))
        d.text((X, Y), f"{'ABCDEFGH'[i]}: offset={c['ox']},{c['oy']} réf={c['ref_hits']} uniq={c['uniq']}/{c['tiles']}",
               fill=(255, 255, 120), font=font)
    out = os.path.join(config.QA_DIR, cfg["id"], f"gridcheck_z{r['id']}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    return out


def recon_sheet(cfg):
    """Vérifie la reconstruction d'UNE feuille (sans toucher à la bibliothèque du jeu) : pour chaque zone,
    les tuiles retenues reproduisent-elles les pixels de la carte ? Écrit un aperçu par zone dans
    rpg/pipeline/qa/<id>/recon_zN.png. Renvoie (taux global, détail par zone)."""
    a, regions, info, p = analyze(cfg)
    t = int(p["tile"])
    out_dir = os.path.join(config.QA_DIR, cfg["id"])
    os.makedirs(out_dir, exist_ok=True)
    covered = total = 0
    detail = []
    for r in regions:
        if r.get("skip"):
            continue
        prev = np.zeros((r["rows"] * t, r["cols"] * t, 4), np.uint8)
        for row, col, h, b in region_tiles(a, r, t, opaque_only=cfg["type"] == "map"):
            prev[row * t:(row + 1) * t, col * t:(col + 1) * t] = b.reshape(t, t, 4)
        ox, oy = r["origin"]
        src = a[oy:oy + r["rows"] * t, ox:ox + r["cols"] * t]
        op = src[..., 3] > 0
        same = int(((prev == src).all(-1) & op).sum())
        covered += same; total += int(op.sum())
        Image.fromarray(prev).save(os.path.join(out_dir, f"recon_z{r['id']}.png"))
        detail.append((r["id"], round(same / max(1, int(op.sum())), 3)))
    return covered / max(1, total), detail
