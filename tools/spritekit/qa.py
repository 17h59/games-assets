"""Contrôle qualité : anomalies en texte + planches PNG numérotées pour vérification visuelle."""
import json
import os
from collections import Counter

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import config

COLORS = {"sprite": (0, 220, 0), "text": (255, 40, 40), "panel": (255, 0, 255), "junk": (255, 220, 0),
          "tiny": (150, 150, 150), "dropped": (255, 140, 0), "entity": (40, 120, 255), "zone": (0, 230, 255)}
MAX_PAGE = 1400


def _font(size=10):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def flags(res, cfg):
    """Liste des anomalies détectées automatiquement."""
    out = list(res["warnings"])
    sprites = [it for it in res["items"] if it["kind"] == "sprite"]
    if not sprites:
        out.append({"flag": "empty", "msg": "aucun sprite gardé"})
        return out
    if len(sprites) >= 8:
        mw = float(np.median([it["w"] for it in sprites]))
        mh = float(np.median([it["h"] for it in sprites]))
        for it in sprites:
            if it["w"] > 2.2 * mw or it["h"] > 2.2 * mh:
                out.append({"flag": "big", "item": it["id"], "x": it["x"], "y": it["y"],
                            "msg": f"{it['w']}x{it['h']} >> médiane {mw:.0f}x{mh:.0f} : sprites fusionnés ? décor ?"})
            elif it["w"] < 0.4 * mw and it["h"] < 0.4 * mh:
                out.append({"flag": "small", "item": it["id"], "x": it["x"], "y": it["y"],
                            "msg": f"{it['w']}x{it['h']} << médiane : morceau détaché ? débris ?"})
    # fond resté opaque : une seule couleur domine les pixels gardés
    a = res["_arrays"][0]
    opaque = a[a[..., 3] > 0][:, :3]
    if len(opaque):
        top, cnt = Counter(map(tuple, opaque[:: max(1, len(opaque) // 100000)])).most_common(1)[0]
        frac = cnt / len(opaque[:: max(1, len(opaque) // 100000)])
        if frac > 0.35 and cfg["type"] not in ("tileset", "map"):
            out.append({"flag": "bg_suspect", "msg": f"la couleur #{'%02X%02X%02X' % top} couvre {frac:.0%} "
                                                     "des pixels gardés : fond pas retiré ? (param bg / bg_tol)"})
    for g in res["info"].get("grid", []):
        if g.get("mode") == "grille" and g.get("conf", 1) < 0.7 and not g.get("forced"):
            bx, by = g["box"][:2]
            out.append({"flag": "grid_cuts", "x": bx, "y": by,
                        "msg": f"grille {g.get('pitch')} du bloc {g['block']} (zone {g.get('zone')}) coupe des sprites "
                               f"(confiance {g['conf']}) : mauvais pas/origine ? (grid_pitch, grid_origin, layout)"})
    # revue C6 : effet plein écran (météo...) pulvérisé en centaines de gouttes identiques, ou sprites
    # isolés sans aucune entité sur une feuille d'effets / de monstres / de personnages
    if cfg["category"] in ("effects", "monsters", "characters") or cfg["type"] == "characters":
        dup = sum(1 for it in sprites if it.get("duplicate_of") is not None)
        if len(sprites) >= 60 and dup > 0.5 * len(sprites):
            out.append({"flag": "pulverise", "msg": f"{dup}/{len(sprites)} sprites sont des doublons : effet plein "
                        "écran découpé goutte par goutte ? (un écran par encadré : `set ID panel_frames=true peel=0`)"})
        if cfg["category"] == "effects" and len(sprites) >= 30 and not res["entities"]:
            out.append({"flag": "no_entity", "msg": f"{len(sprites)} sprites et AUCUNE animation : les frames d'un "
                        "effet / d'un monstre / d'un perso doivent être regroupées (group=..., sk entity)"})
    if res["entities"]:
        sizes = Counter(len(e["frames"]) for e in res["entities"])
        allowed = {res["params"]["frames"], *res["params"]["frames_alt"]}
        if set(sizes) - allowed:
            out.append({"flag": "frame_counts", "msg": f"nombre de frames par entité variable : {dict(sizes)}"})
    return out


def text_report(res, cfg, fl, verbose=False):
    kinds = Counter(it["kind"] for it in res["items"])
    lines = [f"feuille {cfg['id']} [{cfg['game']}/{cfg['category']}] « {cfg['title']} » type={cfg['type']}",
             f"fond retiré : {', '.join(res['info']['bg']['removed']) or ('déjà transparent' if res['info']['bg']['already_transparent'] else 'rien')}",
             "items : " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())),
             f"entités : {len(res['entities'])}" if res["entities"] else "entités : - (group=none)"]
    zones = res["info"].get("zones", [])
    if zones:
        lines.append("zones : " + " | ".join(f"Z{z['zone']} {z['box']} " + ("ignorée" if z["skip"] else json.dumps(z["params"]))
                                              for z in zones))
    junk = Counter(it.get("junk") for it in res["items"] if it["kind"] == "junk")
    if junk:
        lines.append("déchets auto : " + ", ".join(f"{k}={v}" for k, v in junk.items()))
    mir = sum(1 for it in res["items"] if "mirror_of" in it) + sum(
        1 for e in res["entities"] for f in e["frames"] if "mirror_of" in f)
    dup = sum(1 for it in res["items"] if "duplicate_of" in it)
    if mir or dup:
        lines.append(f"miroirs : {mir}  doublons internes : {dup}  (=m / =d sur la planche results)")
    forced = [g for g in res["info"].get("grid", []) if g.get("forced")]
    if forced:
        lines.append(f"grille imposée sur {len(forced)} bloc(s) : vérifier à l'œil sur results que chaque case = un élément")
    modes = Counter(g["mode"] for g in res["info"].get("grid", []))
    if modes:
        lines.append("disposition : " + ", ".join(f"{n} bloc(s) {m}" for m, n in modes.items())
                     + "  (grille/xycut = découpage par cases, taches = sprite par sprite)")
    if res["info"]["override_log"]:
        lines.append("corrections non appliquées : " + " | ".join(res["info"]["override_log"]))
    lines.append(f"anomalies : {len(fl)}")
    for f in fl[:40]:
        where = f" item {f['item']}" if "item" in f else ""
        pos = f" @({f['x']},{f['y']})" if "x" in f else ""
        lines.append(f"  - [{f['flag']}]{where}{pos} {f['msg']}")
    if len(fl) > 40:
        lines.append(f"  ... {len(fl) - 40} autres")
    if verbose:
        for it in res["items"]:
            lines.append(f"  #{it['id']:4d} {it['kind']:7s} {it['x']},{it['y']} {it['w']}x{it['h']}")
    return "\n".join(lines)


def _checker(w, h, s=8):
    yy, xx = np.mgrid[0:h, 0:w]
    c = (((yy // s) + (xx // s)) % 2) * 40 + 190
    return Image.fromarray(np.stack([c, c, c, np.full_like(c, 255)], -1).astype(np.uint8))


def overview(res, cfg, out_dir, scale=None, region=None):
    """Feuille d'origine (fond retiré) avec boîtes et numéros. Découpée en pages si grande."""
    a = res["_arrays"][0]
    h, w = a.shape[:2]
    if scale is None:
        scale = 3 if max(w, h) <= 400 else 2 if max(w, h) <= 1200 else 1
    x0, y0, x1, y1 = (0, 0, w, h) if region is None else region
    img = _checker((x1 - x0) * scale, (y1 - y0) * scale)
    sheet = Image.fromarray(a[y0:y1, x0:x1]).resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST)
    img.alpha_composite(sheet)
    d = ImageDraw.Draw(img)
    font = _font(10 if scale >= 2 else 8)

    def box(x, y, bw, bh, color, label, width=1):
        X0, Y0 = (x - x0) * scale, (y - y0) * scale
        d.rectangle([X0 - 1, Y0 - 1, X0 + bw * scale, Y0 + bh * scale], outline=color, width=width)
        if label is not None:
            tw = d.textlength(label, font=font)
            d.rectangle([X0 - 1, Y0 - 11, X0 + tw + 1, Y0 - 1], fill=(0, 0, 0))
            d.text((X0, Y0 - 11), label, fill=color, font=font)

    for z in res["info"].get("zones", []):
        zx, zy, zw, zh = z["box"]
        box(zx - 2, zy - 2, zw + 4, zh + 4, COLORS["zone"], f"Z{z['zone']}" + (" ignorée" if z["skip"] else ""), 3)
    for e in res["entities"]:
        bx, by, bw, bh = e["box"]
        box(bx - 1, by - 1, bw + 2, bh + 2, COLORS["entity"], None, 2)
    for it in res["items"]:
        lbl = str(it["id"]) if it["kind"] != "tiny" else None
        box(it["x"], it["y"], it["w"], it["h"], COLORS[it["kind"]], lbl)
    for e in res["entities"]:
        bx, by, bw, bh = e["box"]
        X0, Y0 = (bx - x0) * scale, (by + bh - y0) * scale + 1
        d.text((X0, Y0), f"e{e['id']}", fill=COLORS["entity"], font=font, stroke_width=2, stroke_fill=(0, 0, 0))

    paths = []
    W, H = img.size
    stem = "overview" if region is None else f"zoom_{x0}_{y0}_{x1}_{y1}"
    for py in range(0, H, MAX_PAGE):
        for px in range(0, W, MAX_PAGE):
            p = os.path.join(out_dir, f"{stem}_{py // MAX_PAGE}_{px // MAX_PAGE}.png")
            img.crop((px, py, min(W, px + MAX_PAGE), min(H, py + MAX_PAGE))).save(p)
            paths.append(p)
    return paths


def montage(res, cfg, out_dir):
    """Planche des résultats : une ligne par entité, ou une grille d'items, agrandis et numérotés."""
    out = config.out_dir(cfg)
    font = _font(10)
    tiles = []
    for e in res["entities"]:
        tiles.append((f"e{e['id']}", Image.open(os.path.join(out, e["file"])).convert("RGBA")))
    for it in res["items"]:
        if it["kind"] == "sprite" and "file" in it:
            tag = " =m" if "mirror_of" in it else " =d" if "duplicate_of" in it else ""
            tiles.append((f"{it['id']}{tag}", Image.open(os.path.join(out, it["file"])).convert("RGBA")))
    if not tiles:
        return []
    # échelle choisie sur la hauteur (bandes d'entités) ou le plus grand côté (items isolés)
    big = int(np.median([t.height if res["entities"] else max(t.size) for _, t in tiles]))
    scale = max(1, min(4, 72 // max(1, big)))
    pad, lab_h = 6, 12
    paths, page, x, y, row_h = [], [], 0, 0, 0
    placed = []
    # un élément plus grand qu'une page (cadre, grand décor) est réduit pour tenir (bug trouvé par un agent :
    # page vide -> plantage)
    limit = MAX_PAGE - 2 * pad - lab_h
    tiles = [(n, t if max(t.width, t.height) * scale <= limit else
              t.resize((max(1, t.width * limit // (max(t.width, t.height) * scale)),
                        max(1, t.height * limit // (max(t.width, t.height) * scale))), Image.NEAREST))
             for n, t in tiles]
    for name, t in tiles:
        tw, th = t.width * scale, t.height * scale
        cw = max(tw, 30) + pad
        if x + cw > MAX_PAGE:
            x, y = 0, y + row_h
            row_h = 0
        if y + th + lab_h + pad > MAX_PAGE and page:
            placed.append(page); page, x, y, row_h = [], 0, 0, 0
        page.append((name, t, x, y))
        x += cw
        row_h = max(row_h, th + lab_h + pad)
    if page:
        placed.append(page)
    for pi, page in enumerate(placed):
        W = max(x + max(t.width * scale, 30) for _, t, x, _ in page) + pad
        H = max(y + t.height * scale + lab_h for _, t, _, y in page) + pad
        img = Image.new("RGBA", (W, H), (60, 60, 70, 255))
        d = ImageDraw.Draw(img)
        for name, t, x, y in page:
            tw, th = t.width * scale, t.height * scale
            img.alpha_composite(_checker(tw, th, 4), (x, y + lab_h))
            img.alpha_composite(t.resize((tw, th), Image.NEAREST), (x, y + lab_h))
            d.text((x, y), name, fill=(255, 255, 120), font=font)
        p = os.path.join(out_dir, f"results_{pi}.png")
        img.save(p)
        paths.append(p)
    return paths


def render(res, cfg, region=None, scale=None):
    out_dir = os.path.join(config.QA_DIR, cfg["id"])
    os.makedirs(out_dir, exist_ok=True)
    if region is None:
        for f in os.listdir(out_dir):
            if f.endswith(".png"):
                os.remove(os.path.join(out_dir, f))
        return overview(res, cfg, out_dir, scale) + montage(res, cfg, out_dir)
    return overview(res, cfg, out_dir, scale or 4, region)


def captions(res, cfg, out_dir, dist=48):
    """Pour chaque entité (ou item isolé s'il n'y a pas d'entité) : la légende du ripper la plus proche
    (texte jeté situé au-dessus ou à gauche, à moins de `dist` px), agrandie, à côté de la 1re frame.
    Sert à nommer les animations (sk name ID eN nom) : il n'y a pas d'OCR, l'agent lit la planche."""
    a = res["_arrays"][0]
    if res.get("sets"):
        return _set_captions(res, a, out_dir)
    texts = [it for it in res["items"] if it["kind"] == "text"]
    targets = [("e%d" % e["id"], e["box"]) for e in res["entities"]] or \
              [(str(it["id"]), [it["x"], it["y"], it["w"], it["h"]]) for it in res["items"] if it["kind"] == "sprite"]
    rows = []
    for name, (bx, by, bw, bh) in targets:
        near = [t for t in texts
                if t["y"] + t["h"] <= by + bh and t["x"] <= bx + bw and t["x"] + t["w"] >= bx - dist
                and by - (t["y"] + t["h"]) <= dist and bx - (t["x"] + t["w"]) <= dist]
        if not near:
            continue
        # la ligne de texte la plus proche (même bas) et tous ses morceaux
        best = min(near, key=lambda t: (by - (t["y"] + t["h"])) ** 2 + (bx - t["x"]) ** 2)
        line = [t for t in near if abs((t["y"] + t["h"]) - (best["y"] + best["h"])) <= 3]
        x0 = min(t["x"] for t in line); y0 = min(t["y"] for t in line)
        x1 = max(t["x"] + t["w"] for t in line); y1 = max(t["y"] + t["h"] for t in line)
        rows.append((name, a[y0:y1, x0:x1], a[by:by + bh, bx:bx + min(bw, bh * 2)]))
    if not rows:
        return []
    font = _font(12)
    paths, page, y = [], [], 0
    sc = 3
    for name, cap, frame in rows:
        h = max(cap.shape[0] * sc, min(frame.shape[0], 48) * 2, 16) + 8
        if y + h > MAX_PAGE and page:
            paths.append(page); page, y = [], 0
        page.append((name, cap, frame, y)); y += h
    paths.append(page)
    out = []
    for pi, page in enumerate(paths):
        H = max(y + max(c.shape[0] * sc, min(f.shape[0], 48) * 2, 16) + 8 for _, c, f, y in page)
        img = Image.new("RGBA", (MAX_PAGE, H), (50, 50, 60, 255))
        d = ImageDraw.Draw(img)
        for name, cap, frame, y in page:
            d.text((4, y + 2), name, fill=(255, 255, 120), font=font)
            ci = Image.fromarray(cap).convert("RGBA")
            ci = ci.resize((min(ci.width * sc, 900), ci.height * sc), Image.NEAREST)
            img.alpha_composite(_checker(ci.width, ci.height, 4), (60, y))
            img.alpha_composite(ci, (60, y))
            fi = Image.fromarray(frame).convert("RGBA")
            k = max(1, min(2, 96 // max(1, fi.height)))
            fi = fi.resize((fi.width * k, fi.height * k), Image.NEAREST)
            img.alpha_composite(fi, (min(980, 70 + ci.width), y))
        path = os.path.join(out_dir, f"captions_{pi}.png")
        img.save(path)
        out.append(path)
    return out


def _set_captions(res, a, out_dir):
    """Une ligne par ensemble : S<n>, nom actuel, légende agrandie, puis les premiers sprites de l'ensemble."""
    font = _font(12)
    sprites = [it for it in res["items"] if it["kind"] == "sprite"]
    rows = []
    for st in res["sets"]:
        x, y, w, h = st["box"]
        members = [it for it in sprites if it.get("set") == st["id"]][:8]
        rows.append((st, a[y:y + h, x:x + w], members))
    out, page, ypos = [], [], 0
    for r in rows:
        if ypos + 70 > MAX_PAGE and page:
            out.append(page); page, ypos = [], 0
        page.append((r, ypos)); ypos += 70
    if page:
        out.append(page)
    paths = []
    for pi, page in enumerate(out):
        img = Image.new("RGBA", (MAX_PAGE, len(page) * 70 + 4), (50, 50, 60, 255))
        d = ImageDraw.Draw(img)
        for (st, cap, members), y in page:
            n = len([1 for it in sprites if it.get("set") == st["id"]])
            d.text((4, y + 2), f"S{st['id']}  {st['name'] or '(sans nom)'}  [{n} sprites]", fill=(255, 255, 120), font=font)
            ci = Image.fromarray(cap).convert("RGBA")
            ci = ci.resize((min(ci.width * 2, 290), ci.height * 2), Image.NEAREST)
            # sur fond noir puis sur fond blanc : lisible quelle que soit la couleur du texte
            img.alpha_composite(Image.new("RGBA", ci.size, (0, 0, 0, 255)), (4, y + 18))
            img.alpha_composite(ci, (4, y + 18))
            img.alpha_composite(Image.new("RGBA", ci.size, (255, 255, 255, 255)), (300, y + 18))
            img.alpha_composite(ci, (300, y + 18))
            x = 620
            for it in members:
                sp = Image.fromarray(a[it["y"]:it["y"] + it["h"], it["x"]:it["x"] + it["w"]]).convert("RGBA")
                k = max(1, min(2, 48 // max(1, sp.height)))
                sp.thumbnail((96, 48))
                if x + sp.width > MAX_PAGE:
                    break
                img.alpha_composite(sp, (x, y + 18)); x += sp.width + 6
        path = os.path.join(out_dir, f"captions_{pi}.png")
        img.save(path)
        paths.append(path)
    return paths
