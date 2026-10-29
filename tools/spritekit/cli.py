"""Ligne de commande `sk` : voir AGENT_GUIDE.md pour le mode d'emploi complet."""
import argparse
import json
import time
import os
import re
import sys
from collections import Counter

from . import auto, checks, config, dupes, extract, journal, objects, qa, tiles

# --------------------------------------------------------------------------- init

EXCLUDE_TITLE = re.compile(
    r"title screen|credits|startup|file select|unused|hoenn map|contest|slots|dodrio|copyright|"
    r"battle intro|moving truck|pok[eé]mon menu|box system|sword scroll|the legend of the minish|"
    r"figurines|^text$|^intro|clock screen|text entry|box connection|starter|debug|world map|"
    r"friend area map|flag designs|portraits", re.I)

# (section, titre ou None, catégorie, type)
RULES = [
    (r"^(Playable|Non-Playable) Characters$", None, "characters", "characters"),
    (r"^(Enemies|Bosses)$", None, "monsters", "sprites"),
    (r"^Pok[eé]mon", None, None, "skip"),
    (r"^Tilesets$", None, "tilesets", "tileset"),
    (r"^Dungeon Tiles$", None, "tilesets", "tileset"),
    (r"^Miscellaneous$", r"exterior tileset|interior tilesets|animated tiles", "tilesets", "tileset"),
    (r"^Gyms$|^Locations$|^Maps$|^Backgrounds|^Dungeons|^Dungeon Boss Rooms$|^Friend Areas$|^Huts$",
     None, "maps", "map"),
    (r"^Miscellaneous$", r"interior areas", "maps", "map"),
    (r"^Battle Effects$|^Attacks$|^Weather$", None, "effects", "sprites"),
    (r"^Miscellaneous$", r"effects|sfx|explosion|droplet|steam|sword \(attacking\)", "effects", "sprites"),
    (r"^Miscellaneous$", r"item icons|pok[eé] balls|map objects|mail|^bag$|bakery products|kinstones|^items$|"
                         r"miscellaneous objects|mushroom|bound chest|berries|berry trees|dolls", "items", "sprites"),
    (r"^Miscellaneous$", r"interface|route icons|pok[eé]dex|type|backgrounds and overlays|fonts and menus|"
                         r"^hud$|^font$|^menu font$|trainer card", "ui", "sprites"),
    (r"^Events$|^Pok[eé]mon Square$", None, "ui", "sprites"),
]
RULES = [(re.compile(s, re.I), re.compile(t, re.I) if t else None, c, ty) for s, t, c, ty in RULES]


def classify(section, title):
    if EXCLUDE_TITLE.search(title):
        return None, "skip"
    for s, t, c, ty in RULES:
        if s.search(section) and (t is None or t.search(title)):
            return c, ty
    return None, "skip"


def cmd_init(args):
    made = 0
    for game_dir, game in config.GAMES.items():
        gpath = os.path.join(config.RAW, game_dir)
        if not os.path.isdir(gpath):
            continue
        for section in sorted(os.listdir(gpath)):
            spath = os.path.join(gpath, section)
            if not os.path.isdir(spath):
                continue
            for fname in sorted(os.listdir(spath)):
                m = re.match(r"(.+)_(\d+)\.(png|gif)$", fname, re.I)
                if not m:
                    continue
                title, sid = m.group(1), m.group(2)
                if os.path.exists(config.sheet_path(game, sid)) and not args.force:
                    continue
                cat, ty = classify(section, title)
                cfg = {"id": sid, "game": game, "section": section, "title": title,
                       "src": os.path.relpath(os.path.join(spath, fname), config.PROJECT),
                       "category": cat or "excluded", "type": ty,
                       "status": "skip" if ty == "skip" else "todo",
                       "params": {}, "overrides": config.empty_overrides(), "notes": ""}
                if ty == "characters" and game in ("emerald", "ruby_sapphire"):
                    cfg["params"] = {"group": "chunks", "frames": 9, "template": "pokemon_ow9"}
                config.save(cfg)
                made += 1
    print(f"{made} fiche(s) créée(s) dans {config.SHEETS}")


# --------------------------------------------------------------------------- consultation

def cmd_list(args):
    rows = []
    for c in config.all_sheets():
        if args.game and c["game"] != args.game: continue
        if args.status and c["status"] != args.status: continue
        if args.type and c["type"] != args.type: continue
        if args.category and c["category"] != args.category: continue
        rows.append(c)
    for c in rows:
        print(f"{c['id']:>7}  {c['game']:13s} {c['category']:10s} {c['type']:10s} {c['status']:12s} {c['title']}")
    print(f"-- {len(rows)} feuille(s)")


def cmd_summary(args):
    cnt = Counter((c["type"], c["status"]) for c in config.all_sheets())
    for (t, s), n in sorted(cnt.items()):
        print(f"{t:10s} {s:12s} {n}")


def cmd_show(args):
    print(json.dumps(config.load(args.id), indent=1, ensure_ascii=False))


def _parse_value(v):
    for conv in (int, float):
        try:
            return conv(v)
        except ValueError:
            pass
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if "," in v and v.startswith("#"):
        return v.split(",")
    if v.startswith("[") or v.startswith("{"):
        return json.loads(v)
    return v


def cmd_set(args):
    cfg = config.load(args.id)
    for kv in args.pairs:
        k, _, v = kv.partition("=")
        if k == "status":  # revue C1 : le statut passe par `sk status` (contrôle des étapes + marqueurs)
            raise SystemExit("le statut se change avec : tools/sk status ID ok|needs_fix|skip \"note\"")
        if k in ("type", "category", "title") and _agent():
            raise SystemExit(f"{k} : réservé au développeur (un agent ne change pas le type d'une feuille)")
        if k in ("type", "category", "notes", "title"):
            cfg[k] = v
        elif k in config.DEFAULT_PARAMS:
            if v == "default":
                cfg["params"].pop(k, None)
            else:
                cfg["params"][k] = _parse_value(v)
        else:
            raise SystemExit(f"paramètre inconnu : {k}. Connus : {', '.join(config.DEFAULT_PARAMS)}")
    config.save(cfg)
    print("ok :", json.dumps(cfg["params"], ensure_ascii=False), "| type", cfg["type"], "| statut", cfg["status"])


# --------------------------------------------------------------------------- exécution

def _run_tiles(cfg, args):
    a, regions, info, p = tiles.analyze(cfg)
    t = int(p["tile"])
    print(f"feuille {cfg['id']} [{cfg['game']}/{cfg['category']}] « {cfg['title']} » type={cfg['type']} tuile={t}px")
    print(f"fond retiré : {', '.join(info['removed']) or ('déjà transparent' if info['already_transparent'] else 'rien')}")
    flags = 0
    for r in regions:
        if r.get("skip"):
            print(f"  z{r['id']:<3d} {r['x']},{r['y']} {r['w']}x{r['h']}  IGNORÉE ({r.get('auto_skip', 'manuel')})")
            continue
        st = r.get("stats")
        extra = f"uniques={st[3]}/{st[2]} partielles={st[1]}" if st else "réglage manuel"
        warn = ""
        if r["conf"] < 0.3 and cfg["type"] == "map" and st and st[2] >= 20:
            warn = "  <- grille peu sûre, vérifier"; flags += 1
        print(f"  z{r['id']:<3d} {r['x']},{r['y']} {r['w']}x{r['h']}  grille=({r['ox']},{r['oy']}) "
              f"{r['cols']}x{r['rows']} conf={r['conf']:.2f} [{r.get('method', 'manuel')}] {extra}{warn}")
    if not args.no_images:
        paths = tiles.render(cfg, a, regions, p)
        print("planches :", " ".join(os.path.relpath(x, config.PROJECT) for x in paths))
    cfg = config.load(cfg["id"])
    # revue I7 : ne pas rétrograder une conclusion (ok encore valide, needs_fix, skip)
    if not (cfg["status"] in ("needs_fix", "skip") or (cfg["status"] in ("ok", "auto_ok") and not checks.missing(cfg))):
        cfg["status"] = "needs_review" if flags else "extracted"
    cfg["run_state"] = checks.state(cfg)
    config.save(cfg)


def _run_one(sid, args):
    cfg = config.load(sid)
    if cfg["type"] in ("map", "tileset"):
        return _run_tiles(cfg, args)
    if cfg["type"] == "objects":
        return _run_objects(cfg, args)
    if cfg["type"] == "terrainset":
        return _run_terrainset(cfg, args)
    if cfg["type"] == "terrainpairs":
        return _run_terrainpairs(cfg, args)
    if cfg["type"] not in ("sprites", "characters"):
        print(f"{sid}: type {cfg['type']} : rien à faire")
        return
    res = extract.run(cfg, write=True)
    fl = qa.flags(res, cfg)
    print(qa.text_report(res, cfg, fl, verbose=args.verbose))
    if not args.no_images:
        paths = qa.render(res, cfg)
        print("planches :", " ".join(os.path.relpath(p, config.PROJECT) for p in paths))
    print(f"sortie : {os.path.relpath(config.out_dir(cfg), config.PROJECT)}")
    cfg = config.load(sid)
    if not (cfg["status"] in ("needs_fix", "skip") or (cfg["status"] in ("ok", "auto_ok") and not checks.missing(cfg))):
        cfg["status"] = "needs_review" if fl else "extracted"
    config.save(cfg)
    auto.refresh_marker(cfg)
    journal.log("run", sid, sprites=sum(1 for it in res["items"] if it["kind"] == "sprite"),
                entities=len(res["entities"]), anomalies=len(fl))


def cmd_run(args):
    for sid in args.ids:
        _run_one(sid, args)
        print()


def cmd_zoom(args):
    cfg = config.load(args.id)
    res = extract.run(cfg, write=False)
    x0, y0, x1, y1 = map(int, args.region.split(","))
    for p in qa.render(res, cfg, region=(x0, y0, x1, y1), scale=args.scale):
        print(os.path.relpath(p, config.PROJECT))


def _last(sid):
    p = os.path.join(config.QA_DIR, sid, "last_run.json")
    if not os.path.exists(p):
        raise SystemExit(f"lance d'abord `sk run {sid}`")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _point_for(item, items):
    """Un point qui désigne cet item sans ambiguïté (le plus petit item contenant le point)."""
    def owner(x, y):
        hits = [it for it in items if it["x"] <= x < it["x"] + it["w"] and it["y"] <= y < it["y"] + it["h"]]
        return min(hits, key=lambda it: it["w"] * it["h"])["id"] if hits else None
    cx, cy = item["x"] + item["w"] // 2, item["y"] + item["h"] // 2
    if owner(cx, cy) == item["id"]:
        return [cx, cy]
    for yy in range(item["y"], item["y"] + item["h"]):
        for xx in range(item["x"], item["x"] + item["w"]):
            if owner(xx, yy) == item["id"]:
                return [xx, yy]
    return [cx, cy]


def _resolve(sid, refs):
    """'12' -> item 12 ; 'e3' -> toutes les frames de l'entité 3. Renvoie des points."""
    last = _last(sid)
    items = {it["id"]: it for it in last["items"]}
    pts = []
    for r in refs:
        if r.startswith("e"):
            ent = next((e for e in last["entities"] if e["id"] == int(r[1:])), None)
            if ent is None:
                raise SystemExit(f"entité inconnue : {r}")
            pts += [_point_for(items[f["item"]], last["items"]) for f in ent["frames"]]
        else:
            if int(r) not in items:
                raise SystemExit(f"item inconnu : {r}")
            pts.append(_point_for(items[int(r)], last["items"]))
    return pts


def _edit(sid, fn):
    cfg = config.load(sid)
    cfg.setdefault("overrides", config.empty_overrides())
    for k, v in config.empty_overrides().items():
        cfg["overrides"].setdefault(k, v)
    fn(cfg["overrides"])
    config.save(cfg)
    print("corrections :", json.dumps({k: v for k, v in cfg["overrides"].items() if v}, ensure_ascii=False))


def cmd_drop(args):
    _edit(args.id, lambda o: o["drop"].extend(_resolve(args.id, args.refs)))


def cmd_keep(args):
    _edit(args.id, lambda o: o["keep"].extend(_resolve(args.id, args.refs)))


def cmd_split(args):
    _edit(args.id, lambda o: o["split"].extend(_resolve(args.id, args.refs)))


def cmd_cut(args):
    _edit(args.id, lambda o: o["cut"].extend(_resolve(args.id, args.refs)))


def cmd_merge(args):
    _edit(args.id, lambda o: o["merge"].append(_resolve(args.id, args.refs)))


def cmd_add(args):
    box = list(map(int, args.box.split(",")))
    _edit(args.id, lambda o: o["add"].append(box))


def cmd_carve(args):
    box = list(map(int, args.box.split(",")))
    if len(box) != 4:
        raise SystemExit("boîte attendue : x,y,w,h")
    _edit(args.id, lambda o: o.setdefault("carve", []).append(box))


def _src(sid):
    import numpy as np
    from PIL import Image
    cfg = config.load(sid)
    return cfg, np.array(Image.open(os.path.join(config.PROJECT, cfg["src"])).convert("RGBA"))


def cmd_pixel(args):
    """Couleur(s) de l'image SOURCE : un point x,y, ou les couleurs d'un rectangle x,y,w,h."""
    from . import imageops
    cfg, raw = _src(args.id)
    v = list(map(int, args.where.split(",")))
    H, W = raw.shape[:2]
    if len(v) == 2:
        x, y = v
        if not (0 <= x < W and 0 <= y < H):
            raise SystemExit(f"hors de la feuille ({W}x{H})")
        c = raw[y, x]
        print(f"({x},{y}) {imageops.rgb_to_hex(c)} alpha={c[3]}")
        return
    x, y, w, h = v
    sub = raw[max(0, y):y + h, max(0, x):x + w].reshape(-1, 4)
    cnt = Counter(imageops.rgb_to_hex(c) + ("" if c[3] == 255 else f"/a{c[3]}") for c in sub)
    print(f"rectangle {x},{y},{w},{h} : {len(sub)} pixels, {len(cnt)} couleurs")
    for col, n in cnt.most_common(args.top):
        print(f"  {col}  {n:6d}  {100 * n / len(sub):5.1f} %")
    print("fond détecté (bord de la feuille) :", [imageops.rgb_to_hex(c) for c in imageops.border_colors(raw)])


def cmd_erase(args):
    """Gomme : pixels du rectangle (de ces couleurs seulement si données) -> transparents, ou remplacés par le
    fond voisin (--fill near) / le motif répété (--fill 16x16) avant le retrait du fond."""
    box = list(map(int, args.box.split(",")))
    if len(box) != 4:
        raise SystemExit("boîte attendue : x,y,w,h")
    if args.fill not in ("clear", "near") and not re.fullmatch(r"\d+x\d+", args.fill):
        raise SystemExit("--fill : clear | near | LxH (période du motif, ex. 16x16)")
    colors = []
    for c in args.colors:
        if not re.fullmatch(r"#?[0-9A-Fa-f]{6}", c):
            raise SystemExit(f"couleur attendue #RRGGBB : {c}")
        colors.append("#" + c.lstrip("#").upper())
    e = {"box": box, "colors": colors, "tol": args.tol, "fill": args.fill}
    from . import imageops
    _, raw = _src(args.id)
    n = int(imageops._erase_mask(raw, e).sum())
    print(f"{n} pixel(s) visé(s)")
    if not n:
        raise SystemExit("aucun pixel visé : rien enregistré (vérifie la boîte et les couleurs avec sk pixel)")
    _edit(args.id, lambda o: o["erase"].append(e))


def cmd_flood(args):
    """Rend transparente la région connexe de la couleur du point (fond d'un panneau, tracé, fond troué...)."""
    pt = list(map(int, args.point.split(",")))
    from . import imageops
    _, raw = _src(args.id)
    m = imageops.flood_mask(raw, pt, args.tol)
    n = int(m.sum())
    if not n:
        raise SystemExit("point hors de la feuille")
    import numpy as np
    ys, xs = np.nonzero(m)
    print(f"{n} pixel(s) de {imageops.rgb_to_hex(raw[pt[1], pt[0]])}, boîte {xs.min()},{ys.min()},"
          f"{xs.max() - xs.min() + 1},{ys.max() - ys.min() + 1}")
    if n > args.max:
        raise SystemExit(f"plus de {args.max} pixels : rien enregistré (--max pour forcer)")
    _edit(args.id, lambda o: o["flood"].append({"point": pt, "tol": args.tol}))


def cmd_name(args):
    pt = _resolve(args.id, [args.ref])[0]
    _edit(args.id, lambda o: o["names"].append({"point": pt, "name": args.name}))


def cmd_anims(args):
    """sk anims ID eN "walk_down=3,0,4,0 walk_up=5,1,6,1 idle_down=0" : animations nommées d'une entité
    (numéros = position de la frame dans l'entité, 0 = première). Remplace les animations déjà posées."""
    last = _last(args.id)
    ent = next((e for e in last["entities"] if f"e{e['id']}" == args.ref), None)
    if ent is None:
        raise SystemExit(f"entité inconnue : {args.ref} (voir `sk run {args.id} -v`)")
    n = len(ent["frames"])
    amap = {}
    for spec in " ".join(args.spec).split():
        k, _, v = spec.partition("=")
        if not k or not v:
            raise SystemExit("format : nom=i,j,k (ex. walk_down=3,0,4,0)")
        idx = [int(x) for x in v.split(",")]
        if any(i < 0 or i >= n for i in idx):
            raise SystemExit(f"{k} : numéros de frames de 0 à {n - 1}")
        amap[config.slug(k)] = idx
    f0 = ent["frames"][0]["src"]
    pt = [f0[0] + f0[2] // 2, f0[1] + f0[3] // 2]
    def upd(o):
        o.setdefault("anims", [])
        o["anims"][:] = [a for a in o["anims"] if a["point"] != pt] + [{"point": pt, "map": amap}]
    _edit(args.id, upd)


def cmd_zone(args):
    """sk zone ID x,y,w,h clé=valeur... | sk zone ID x,y,w,h skip | sk zone ID del N | sk zone ID list"""
    cfg = config.load(args.id)
    zones = cfg.setdefault("zones", [])
    if args.box == "list":
        for i, z in enumerate(zones):
            print(f"Z{i}: {z['box']} {'IGNORÉE ' if z.get('skip') else ''}{json.dumps(z.get('params', {}))}")
        if not zones:
            print("aucune zone")
        return
    if args.box == "del":
        i = int(args.pairs[0].lstrip("Z"))
        print("supprimée :", zones.pop(i))
        config.save(cfg)
        return
    box = list(map(int, args.box.split(",")))
    if len(box) != 4:
        raise SystemExit("boîte attendue : x,y,w,h")
    z = {"box": box, "params": {}}
    for kv in args.pairs:
        if kv == "skip":
            z["skip"] = True
            continue
        k, _, v = kv.partition("=")
        if k not in config.DEFAULT_PARAMS:
            raise SystemExit(f"paramètre inconnu : {k}")
        z["params"][k] = _parse_value(v)
    zones.append(z)
    config.save(cfg)
    print(f"Z{len(zones) - 1} ajoutée : {json.dumps(z)} (les zones sont prioritaires dans l'ordre de création)")


def cmd_autovalidate(args):
    print(auto.autovalidate(sample=args.sample, dry=args.dry))


def cmd_suggest(args):
    cfg = config.load(args.id)
    sug, n = auto.suggest(cfg)
    print(f"{n} feuille(s) sœur(s) validée(s) ; réglages majoritaires : {json.dumps(sug, ensure_ascii=False)}")
    if args.apply and sug:
        cfg["params"] = {**sug, **cfg.get("params", {})}
        config.save(cfg)
        print("appliqués (les réglages propres de la feuille restent prioritaires)")


def cmd_dupes(args):
    print(dupes.build())


def cmd_clear(args):
    def f(o):
        for k in ([args.what] if args.what != "all" else list(o)):
            o[k] = []
    _edit(args.id, f)


def cmd_region(args):
    """sk region ID zN skip | unskip | offset=ox,oy | auto"""
    cfg = config.load(args.id)
    a, regions, info, p = tiles.analyze(cfg)
    n = int(args.zone.lstrip("z"))
    r = next((r for r in regions if r["id"] == n), None)
    if r is None:
        raise SystemExit(f"zone inconnue : {args.zone}")
    key = f"{r['x'] + r['w'] // 2},{r['y'] + r['h'] // 2}"
    reg = cfg.setdefault("regions", {})
    # retire un ancien réglage qui visait la même zone
    for k in list(reg):
        x, y = map(int, k.split(","))
        if r["x"] <= x < r["x"] + r["w"] and r["y"] <= y < r["y"] + r["h"]:
            del reg[k]
    if args.action == "skip":
        reg[key] = {"skip": True}
    elif args.action == "unskip":
        reg[key] = {"unskip": True}
    elif args.action.startswith("offset="):
        reg[key] = {"offset": list(map(int, args.action.split("=", 1)[1].split(",")))}
    elif args.action != "auto":
        raise SystemExit("action : skip | unskip | offset=ox,oy | auto")
    config.save(cfg)
    print("zones :", json.dumps(reg))


def cmd_gridcheck(args):
    cfg = config.load(args.id)
    a, regions, info, p = tiles.analyze(cfg)
    t = int(p["tile"])
    n = int(args.zone.lstrip("z"))
    r = next((r for r in regions if r["id"] == n), None)
    if r is None:
        raise SystemExit(f"zone inconnue : {args.zone}")
    cands = tiles.candidates(a, r, t, tiles.reference(cfg["game"]))
    print(f"z{n} actuelle : offset={r.get('ox')},{r.get('oy')} conf={r.get('conf', 0):.2f} [{r.get('method', 'manuel')}]")
    for i, c in enumerate(cands):
        print(f"  {'ABCDEFGH'[i]}: offset={c['ox']},{c['oy']}  correspondances_réf={c['ref_hits']}  uniques={c['uniq']}/{c['tiles']}")
    print("planche :", os.path.relpath(tiles.render_candidates(cfg, a, r, t, cands), config.PROJECT))
    print(f"choisir : tools/sk region {args.id} z{n} offset=OX,OY   (ou skip si la zone n'est pas une carte)")


def cmd_recon(args):
    cfg = config.load(args.id)
    if cfg["type"] not in ("map", "tileset"):
        raise SystemExit("sk recon : cartes et tilesets seulement")
    cov, detail = tiles.recon_sheet(cfg)
    print(f"{args.id} : {cov:.1%} des pixels des zones reproduits par les tuiles ; par zone : "
          + ", ".join(f"z{z}={c:.0%}" for z, c in detail))
    print(f"aperçus : rpg/pipeline/qa/{args.id}/recon_zN.png")
    if cov >= 0.97:
        checks.confirm(cfg, "reconstruction", "ok", f"{cov:.1%} reproduits (sk recon)", by="outil")
        config.save(cfg)
        print("étape reconstruction confirmée automatiquement")
    else:
        print("< 97 % : regarde les aperçus ; zones qui ne sont pas des cartes (titres, panneaux) -> sk region ID zN skip ;"
              " zone mal découpée -> sk gridcheck ; si c'est normal (bords transparents d'une carte), "
              f"sk check {args.id} reconstruction ok \"raison\"")


def cmd_tiles(args):
    ref = tiles.reference(args.game, rebuild=True)
    print(f"référence : {len(ref)} tuiles sûres")
    n, k = tiles.build_library(args.game)
    print(f"{args.game} : {n} tuiles uniques depuis {k} feuille(s) -> {os.path.relpath(os.path.join(config.ASSETS, args.game, 'tiles'), config.PROJECT)}")


def cmd_objects(args):
    st = objects.build(args.game)
    print(f"{args.game} : {st}")
    print(f"pages de vérification : tools/sk run {objects.page_id(args.game, 0)} ... (sk list --type objects)")


def _run_terrainset(cfg, args):
    """Table d'autotiles Donjon Mystère : atlas par groupe (murs, sol, eau…) + motifs de voisins."""
    from . import pmd
    res = pmd.extract(cfg)
    if res is None:
        print(f"{cfg['id']} : pas de tableau PMD reconnu (lignes cyan/roses au pas de 25 px) -> needs_fix")
        return
    print(f"{cfg['id']} « {cfg['title']} » : tableau {res['table']['ncols']}x{res['table']['nrows']} cases, "
          f"{res['legend_cells']} motifs de légende")
    for g in res["groups"]:
        print(f"  {g['name']:<14} {len(g['tiles']):3d} tuiles ({g['cols']} colonnes)"
              + (f", {g['sans_legende']} sans motif de légende" if g["sans_legende"] else ""))
    print("noms des groupes : " + ",".join(g["name"] for g in res["groups"])
          + f"  (à corriger d'après l'en-tête : tools/sk set {cfg['id']} pmd_groups='[\"walls\",...]')")
    if not args.no_images:
        print("planches :", " ".join(os.path.relpath(p, config.PROJECT) for p in pmd.montage(cfg, res)))
    print(f"sortie : {os.path.relpath(res['dir'], config.PROJECT)}")
    cfg = config.load(cfg["id"])
    if not (cfg["status"] in ("needs_fix", "skip") or (cfg["status"] in ("ok", "auto_ok") and not checks.missing(cfg))):
        cfg["status"] = "needs_review"
    cfg["run_state"] = checks.state(cfg)
    config.save(cfg)
    journal.log("run", cfg["id"], groupes=len(res["groups"]))


def _run_terrainpairs(cfg, args):
    """Page de bords de terrains (Pokémon) : recalcule les terrains du jeu, liste + planche de la page."""
    from . import terrains
    with config.lock(f"terrains_{cfg['game']}"):
        terrains.build(cfg["game"])
    cfg = config.load(cfg["id"])
    print(terrains.page_report(cfg))
    if not args.no_images:
        print("planches :", " ".join(os.path.relpath(p, config.PROJECT) for p in terrains.montage_page(cfg)))
    if not (cfg["status"] in ("needs_fix", "skip") or (cfg["status"] in ("ok", "auto_ok") and not checks.missing(cfg))):
        cfg["status"] = "needs_review"
    cfg["run_state"] = checks.state(cfg)
    config.save(cfg)
    journal.log("run", cfg["id"])


def cmd_tdrop(args):
    from . import terrains
    with config.lock(f"terrains_{config.load(args.id)['game']}"):
        cfg = config.load(args.id)
        _, rows = terrains.page_pairs(cfg)
        by_n = {n: tr for _, _, trs in rows for n, tr in trs}
        o = cfg.setdefault("overrides", {}).setdefault("drop", [])
        for r in args.refs:
            n = int(r.lstrip("#"))
            if n not in by_n:
                raise SystemExit(f"bord inconnu : #{n} (1 à {len(by_n)})")
            h = by_n[n]["hash"]
            if args.undo:
                o[:] = [x for x in o if x != h]
            elif h not in o:
                o.append(h)
        config.save(cfg)
    print(f"{args.id} : {len(o)} bord(s) jeté(s). `sk run {args.id}` pour revoir.")


def cmd_tname(args):
    from . import terrains
    with config.lock(f"terrains_{config.load(args.id)['game']}"):
        cfg = config.load(args.id)
        res, rows = terrains.page_pairs(cfg)
        ids = {a for a, _, _ in rows} | {b for _, b, _ in rows}
        tid = int(args.terrain)
        if tid not in ids:
            raise SystemExit(f"terrain {tid} absent de cette page (ids : {sorted(ids)})")
        key = next(t["key"] for t in res["terrains"] if t["id"] == tid)
        cfg.setdefault("overrides", {}).setdefault("names", {})[key] = config.slug(args.name)
        config.save(cfg)
    print(f"terrain {tid} -> {config.slug(args.name)}")


def _run_objects(cfg, args):
    """Page d'objets : reconstruit les objets du jeu (corrections comprises), planche + liste."""
    st = objects.build(cfg["game"])
    cfg = config.load(cfg["id"])
    print(objects.page_report(cfg))
    if not args.no_images:
        print("planches :", " ".join(os.path.relpath(p, config.PROJECT) for p in objects.montage_page(cfg)))
    if not (cfg["status"] in ("needs_fix", "skip") or (cfg["status"] in ("ok", "auto_ok") and not checks.missing(cfg))):
        cfg["status"] = "needs_review"
    cfg["run_state"] = checks.state(cfg)
    config.save(cfg)
    journal.log("run", cfg["id"], objets=len(cfg["regions"]["sigs"]), jeu=st)


def _page_sigs(cfg, refs):
    sigs = cfg["regions"]["sigs"]
    try:
        out = [sigs[int(r.lstrip("#")) - 1] for r in refs]
    except (IndexError, ValueError):
        raise SystemExit(f"numéros invalides : 1 à {len(sigs)} (voir la planche de `sk run {cfg['id']}`)")
    return out


def _obj_page(ref):
    cfg = config.load(ref)
    if cfg["type"] != "objects":
        raise SystemExit(f"{ref} n'est pas une page d'objets (obj_<jeu>_NN)")
    cfg.setdefault("overrides", {}).setdefault("drop", []); cfg["overrides"].setdefault("names", {})
    cfg["overrides"].setdefault("split", {})
    return cfg


def cmd_objdrop(args):
    with config.lock(f"objects_{config.load(args.id)['game']}"):
        cfg = _obj_page(args.id)
        for s in _page_sigs(cfg, args.refs):
            if args.undo:
                cfg["overrides"]["drop"] = [x for x in cfg["overrides"]["drop"] if x != s]
            elif s not in cfg["overrides"]["drop"]:
                cfg["overrides"]["drop"].append(s)
        config.save(cfg)
        print(f"{args.id} : {len(cfg['overrides']['drop'])} objet(s) jeté(s) sur cette page. `sk run {args.id}` pour revoir.")


def cmd_objname(args):
    with config.lock(f"objects_{config.load(args.id)['game']}"):
        cfg = _obj_page(args.id)
        s = _page_sigs(cfg, [args.ref])[0]
        cfg["overrides"]["names"][s] = config.slug(args.name)
        config.save(cfg)
        print(f"#{args.ref} -> {config.slug(args.name)}")


def cmd_objsplit(args):
    with config.lock(f"objects_{config.load(args.id)['game']}"):
        cfg = _obj_page(args.id)
        s = _page_sigs(cfg, [args.ref])[0]
        if args.rects == ["undo"]:
            cfg["overrides"]["split"].pop(s, None)
        else:
            rects = []
            for r in args.rects:
                try:
                    x, y, w, h = map(int, r.split(","))
                except ValueError:
                    raise SystemExit("rectangle en TUILES : x,y,l,h (ex. 0,0,2,1 = 2 tuiles en haut à gauche)")
                rects.append([x, y, w, h])
            cfg["overrides"]["split"][s] = rects
        config.save(cfg)
        print(f"#{args.ref} découpé en {len(args.rects)} morceau(x) + le reste. `sk run {args.id}` : les morceaux "
              f"apparaissent sur cette page (nouveaux numéros), jette ceux qui ne servent pas (mur, sol).")


def cmd_status(args):
    cfg = config.load(args.id)
    if args.status not in config.STATUSES:
        raise SystemExit(f"statuts possibles : {config.STATUSES}")
    if args.status == "ok":
        miss = checks.missing(cfg)
        if miss:
            raise SystemExit(f"{args.id} : statut ok REFUSÉ, étapes non confirmées sur l'état actuel de la fiche :\n"
                             + "\n".join(f"  - {st} ({why}) : {checks.STAGES[cfg['type']][st]}" for st, why in miss)
                             + f"\nConfirme chaque étape avec : tools/sk check {args.id} ETAPE ok|na \"note\"")
    cfg["status"] = args.status
    if args.note:
        cfg["notes"] = (cfg.get("notes", "") + "\n" + args.note).strip()
    config.save(cfg)
    auto.refresh_marker(cfg)  # marqueurs NON_VERIFIE / A_VERIFIER dans le dossier d'assets
    print(f"{args.id} -> {args.status}")


def cmd_captions(args):
    cfg = config.load(args.id)
    res = extract.run(cfg, write=False)
    out = os.path.join(config.QA_DIR, cfg["id"])
    os.makedirs(out, exist_ok=True)
    paths = qa.captions(res, cfg, out)
    if not paths:
        print("aucune légende trouvée près des entités / items (étape nommage : « na » si la feuille n'en a pas)")
    for pth in paths:
        print("planche :", os.path.relpath(pth, config.PROJECT))
    if paths:
        print(f"lis chaque légende et nomme : tools/sk name {args.id} eN nom_en_snake_case")


def cmd_setname(args):
    """Nomme un ensemble (légende) : sk setname ID S3 fire_blast ; nom « none » = pas un ensemble."""
    last = _last(args.id)
    k = int(args.ref.lstrip("Ss"))
    st = next((x for x in last.get("sets", []) if x["id"] == k), None)
    if st is None:
        raise SystemExit(f"ensemble inconnu : {args.ref} (lance sk run puis sk captions)")
    _edit(args.id, lambda o: o.setdefault("setnames", []).append({"point": st["point"], "name": args.name}))


def cmd_setbox(args):
    """sk setbox ID Sn x,y,w,h : les sprites dont le centre est dans la boîte rejoignent l'ensemble Sn."""
    last = _last(args.id)
    k = int(args.ref.lstrip("Ss"))
    st = next((x for x in last.get("sets", []) if x["id"] == k), None)
    if st is None:
        raise SystemExit(f"ensemble inconnu : {args.ref}")
    box = list(map(int, args.box.split(",")))
    _edit(args.id, lambda o: o.setdefault("setbox", []).append({"set_point": st["point"], "box": box}))


def cmd_entity(args):
    """sk entity ID 12 13 14 15 : ces items, dans cet ordre, forment une entité (animation)."""
    _edit(args.id, lambda o: o.setdefault("entities", []).append(_resolve(args.id, args.refs)))


def cmd_slice(args):
    """sk slice ID n [cols] [rows] : coupe l'item n en cols x rows parts égales (via carve)."""
    last = _last(args.id)
    it = next((i for i in last["items"] if i["id"] == int(args.ref)), None)
    if it is None:
        raise SystemExit(f"item inconnu : {args.ref}")
    cols, rows = args.cols, args.rows
    boxes = []
    for r in range(rows):
        for c in range(cols):
            x0 = it["x"] + it["w"] * c // cols; x1 = it["x"] + it["w"] * (c + 1) // cols
            y0 = it["y"] + it["h"] * r // rows; y1 = it["y"] + it["h"] * (r + 1) // rows
            boxes.append([x0, y0, x1 - x0, y1 - y0])
    _edit(args.id, lambda o: o.setdefault("carve", []).extend(boxes))


def cmd_regress(args):
    """Après une modification de l'OUTIL : chaque feuille validée (ok / auto_ok) est ré-extraite à blanc et
    comparée à son manifest. Sortie différente (nb d'items ou d'entités) -> needs_review + note, car ses
    confirmations portaient sur une autre sortie. Sinon, avec --write, les fichiers sont régénérés."""
    changed, same, geo = [], 0, []
    for c in list(config.all_sheets()):
        if c["type"] not in ("sprites", "characters") or c["status"] not in ("ok", "auto_ok"):
            continue
        mpath = os.path.join(config.out_dir(c), "manifest.json")
        if not os.path.exists(mpath):
            continue
        with open(mpath, encoding="utf-8") as f:
            man = json.load(f)
        r = extract.run(c, write=False)
        new = (len([i for i in r["items"] if i["kind"] == "sprite" and "file" in i]), len(r["entities"]))
        old = (len(man["items"]), len(man["entities"]))
        cells_new = [list(e.get("cell") or []) for e in r["entities"]]
        cells_old = [list(e.get("cell") or []) for e in man["entities"]]
        if new == old and cells_new != cells_old:
            # même découpage, cases d'animation recalculées (ex. correctif d'alignement) : régénéré, tracé
            geo.append(c["id"])
            diff = sum(1 for a, b in zip(cells_old, cells_new) if a != b)
            extract.run(config.load(c["id"]), write=True)
            journal.log("régression", c["id"], geometrie=diff)
            print(f"  {c['id']} {c['title']} : {diff} case(s) d'animation recalculée(s) (régénérée)")
            continue
        if new != old:
            changed.append(c["id"])
            cfg = config.load(c["id"])
            extract.run(cfg, write=True)
            cfg = config.load(c["id"])
            cfg["status"] = "needs_review"
            cfg["resume"] = True
            # revue C2 : les confirmations portaient sur l'ancienne sortie -> à refaire
            if cfg.get("checks"):
                cfg.setdefault("checks_history", []).append({"regression": time.strftime("%Y-%m-%d %H:%M:%S"),
                                                             "checks": cfg.pop("checks")})
            cfg["notes"] = (cfg.get("notes", "") + f"\nSORTIE MODIFIÉE par une correction de l'outil (items, entités) "
                            f"{old} -> {new} : revérifier et reconfirmer les étapes").strip()
            config.save(cfg)
            auto.refresh_marker(cfg)
            journal.log("régression", c["id"], avant=old, apres=new)
            print(f"  {c['id']} {c['title']} : {old} -> {new} => needs_review")
        else:
            same += 1
            if args.write:
                extract.run(config.load(c["id"]), write=True)
    print(f"{same} identique(s){' (régénérées)' if args.write else ''}, {len(geo)} case(s) recalculée(s), "
          f"{len(changed)} modifiée(s) -> relecture")


def cmd_check(args):
    cfg = config.load(args.id)
    checks.confirm(cfg, args.stage, args.result, args.note or "")
    config.save(cfg)
    miss = checks.missing(cfg)
    print(f"{args.id} : étape {args.stage} = {args.result}" + (f" ; reste : {', '.join(m[0] for m in miss)}" if miss
                                                             else " ; toutes les étapes sont confirmées"))


def cmd_coverage(args):
    """Pour chaque type et chaque étape : combien de feuilles l'ont confirmée sur leur état actuel."""
    from collections import defaultdict
    tab = defaultdict(lambda: defaultdict(int))
    lst = defaultdict(list)
    for c in config.all_sheets():
        if c["status"] == "skip" or c["type"] not in checks.STAGES:
            continue
        if args.game and c["game"] != args.game:
            continue
        miss = dict(checks.missing(c))
        for st in checks.required(c):
            ok = st not in miss
            tab[c["type"]][(st, ok)] += 1
            if not ok:
                lst[(c["type"], st)].append(c["id"])
    for ty in sorted(tab):
        print(f"[{ty}]")
        for st in checks.STAGES[ty]:
            done, todo = tab[ty][(st, True)], tab[ty][(st, False)]
            print(f"  {st:<15} confirmées {done:4d}   à faire {todo:4d}")
            if args.list and lst[(ty, st)]:
                print("     " + " ".join(lst[(ty, st)]))


# commandes qui modifient une fiche ou des fichiers : tracées dans le journal
MUTATING = {"tdrop", "tname", "anims", "set", "drop", "keep", "split", "merge", "cut", "add", "carve", "name", "setname", "setbox", "entity", "slice", "clear", "erase", "flood", "status", "zone", "region", "check",
            "objdrop", "objname", "objsplit", "objects", "autovalidate", "suggest", "init", "regress"}


def _audit_diff(c, t):
    """Nature d'un désaccord d'audit : compare la fiche à sa version sauvegardée (git de rpg/pipeline) au moment
    de l'audit : « découpage » (drop, merge, split…), sinon « regroupement » (entités, animations, params), sinon « noms »."""
    import subprocess
    rel = os.path.relpath(config.sheet_path(c["game"], c["id"]), config.PIPELINE)
    git = ["git", "-C", config.PIPELINE]
    rev = subprocess.run(git + ["log", "-1", f"--before={t}", "--format=%H", "--", rel],
                         capture_output=True, text=True).stdout.strip()
    if not rev:
        return "?: pas de version sauvegardée"
    old = json.loads(subprocess.run(git + ["show", f"{rev}:{rel}"], capture_output=True, text=True).stdout or "{}")
    ov, nv = old.get("overrides", {}), c.get("overrides", {})
    # clé absente = vide (des clés ont été ajoutées depuis, vides : anims, erase…)
    keys = sorted(k for k in set(ov) | set(nv) if (ov.get(k) or None) != (nv.get(k) or None))
    op, np_ = old.get("params", {}), c.get("params", {})
    keys += [f"params.{k}" for k in sorted(set(op) | set(np_)) if op.get(k) != np_.get(k) and k in op]
    if not keys:
        return "statut: " + c["status"] if c["status"] != "ok" else "?: autre"
    cut = {"drop", "keep", "merge", "split", "cut", "carve", "erase", "flood", "setbox", "add"}
    kind = ("découpage" if set(keys) & cut else
            "noms" if set(keys) <= {"names", "setnames"} else "regroupement")
    return f"{kind}: {' '.join(keys)}"


def cmd_audit(args):
    """Revue C7 / idée 4 : fiabilité des validations Haiku. `sk audit --n 10` : tire au hasard N feuilles ok
    dont les confirmations viennent de Haiku (cc:), les renvoie au niveau 1 (Gemini) en relecture, en gardant
    l'état validé. `sk audit --report` : pour chaque feuille auditée et reconclue, l'auditeur a-t-il changé la
    fiche (désaccord) ou confirmé tel quel (accord) ?"""
    import random
    sheets = list(config.all_sheets())
    if args.report:
        agree = dis = pending = 0
        kinds = {}
        for c in sheets:
            a = c.get("audit")
            if not a:
                continue
            if c["status"] not in ("ok", "needs_fix", "skip"):
                pending += 1
                continue
            same = checks.state(c) == a["state"] and c["status"] == "ok"
            agree += same; dis += not same
            what = "" if same else _audit_diff(c, a["t"])
            if what:
                kinds[what.split(":")[0]] = kinds.get(what.split(":")[0], 0) + 1
            print(f"  {c['id']:>8} {c['title'][:30]:<30} {'accord' if same else 'DÉSACCORD'} (statut {c['status']}) {what}")
        print(f"audit : {agree} accord(s), {dis} désaccord(s), {pending} en cours")
        if kinds:
            print("nature des désaccords : " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())))
        return
    pool = [c for c in sheets if c["type"] in (args.type or "sprites characters").split() and c["status"] == "ok"
            and not c.get("audit") and c.get("checks")
            and all(str(v.get("by", "")).startswith("cc:") for v in c["checks"].values())]
    random.seed(args.seed)
    for c in random.sample(pool, min(args.n, len(pool))):
        c["audit"] = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "state": checks.state(c), "checks": c["checks"]}
        c.setdefault("checks_history", []).append({"audit": c["audit"]["t"], "checks": c.pop("checks")})
        c["status"] = "needs_review"; c["level"] = 1; c["attempts"] = 0; c.pop("resume", None)
        config.save(c)
        auto.refresh_marker(c)
        print(f"audit : {c['id']} {c['title']}")


def cmd_godot(args):
    from . import godot
    st = godot.export()
    print(f"catalogue Godot : {st} -> rpg/godot/catalog.json")
    print("ressources : godot --headless --path rpg --script res://godot/tools/build_resources.gd")


def cmd_report(args):
    from . import report
    text = report.build()
    print(text)
    path = os.path.join(config.PIPELINE, "RECAP.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"\n(écrit dans {os.path.relpath(path, config.PROJECT)})")


def cmd_journal(args):
    recs = journal.read(args.id, args.last)
    for r in recs:
        print(journal.fmt(r))
    if not recs:
        print("journal vide" + (f" pour {args.id}" if args.id else ""))


def _agent():
    """Lot d'agent en cours (SK_AGENT = « cc:TAG » / « agy:TAG ») ; None pour le développeur / le répartiteur."""
    a = os.environ.get("SK_AGENT", "")
    return a.split(":", 1)[1] if a.startswith(("cc:", "agy:")) else None


# commandes globales (tout un jeu, toutes les fiches) : interdites aux agents (revue C8)
GLOBAL = {"audit", "godot", "init", "regress", "tiles", "objects", "autovalidate", "reference", "dupes"}


def _guard(args):
    """Revue C8 : un agent ne lance pas de commande globale, et ne modifie que les fiches de SON lot."""
    lot = _agent()
    if not lot:
        return
    if args.cmd in GLOBAL:
        raise SystemExit(f"`sk {args.cmd}` est réservé au développeur (commande globale). Note le besoin dans "
                         f"ta conclusion (`sk status ID needs_fix \"...\"`).")
    if args.cmd in MUTATING and getattr(args, "id", None):
        cfg = config.load(args.id)
        if cfg.get("assigned") and cfg["assigned"] != lot:
            raise SystemExit(f"{args.id} est assignée à un autre lot ({cfg['assigned']}) : ne la modifie pas.")
        if not cfg.get("assigned"):
            raise SystemExit(f"{args.id} ne fait pas partie de ton lot : ne la modifie pas.")
    if args.cmd == "clear" and getattr(args, "what", None) == "all":
        raise SystemExit("`sk clear ID all` est réservé au développeur : efface les catégories une par une.")


def main(argv=None):
    p = argparse.ArgumentParser(prog="sk", description="Découpage de feuilles de sprites. Voir tools/AGENT_GUIDE.md")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="crée les fiches à partir de rpg/_raw"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_init)
    s = sub.add_parser("list", help="liste les feuilles")
    for k in ("game", "status", "type", "category"):
        s.add_argument(f"--{k}")
    s.set_defaults(fn=cmd_list)
    sub.add_parser("summary", help="compte par type et statut").set_defaults(fn=cmd_summary)
    s = sub.add_parser("show", help="affiche la fiche"); s.add_argument("id"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("set", help="modifie des paramètres : sk set ID gap=2 group=chunks ... (valeur 'default' = retirer)")
    s.add_argument("id"); s.add_argument("pairs", nargs="+"); s.set_defaults(fn=cmd_set)
    s = sub.add_parser("run", help="extrait + rapport + planches")
    s.add_argument("ids", nargs="+"); s.add_argument("-v", "--verbose", action="store_true")
    s.add_argument("--no-images", action="store_true"); s.set_defaults(fn=cmd_run)
    s = sub.add_parser("zoom", help="planche agrandie d'une zone : sk zoom ID x0,y0,x1,y1")
    s.add_argument("id"); s.add_argument("region"); s.add_argument("--scale", type=int, default=4); s.set_defaults(fn=cmd_zoom)
    for name, fn, hlp in (("drop", cmd_drop, "jeter des items (n ou eN)"), ("keep", cmd_keep, "garder des items jetés"),
                          ("split", cmd_split, "re-découper un item fusionné"), ("merge", cmd_merge, "fusionner des items en un"),
                          ("cut", cmd_cut, "personnages : l'item donné commence une nouvelle entité")):
        s = sub.add_parser(name, help=hlp); s.add_argument("id"); s.add_argument("refs", nargs="+"); s.set_defaults(fn=fn)
    s = sub.add_parser("add", help="boîte forcée x,y,w,h (regroupe tout ce qui est dedans)")
    s.add_argument("id"); s.add_argument("box"); s.set_defaults(fn=cmd_add)
    s = sub.add_parser("carve", help="découpe au pixel près : les pixels du rectangle x,y,w,h deviennent UN item "
                                     "(sprites collés sans aucun pixel transparent entre eux)")
    s.add_argument("id"); s.add_argument("box"); s.set_defaults(fn=cmd_carve)
    s = sub.add_parser("pixel", help="couleur de l'image source : sk pixel ID x,y | sk pixel ID x,y,w,h (couleurs du rectangle)")
    s.add_argument("id"); s.add_argument("where"); s.add_argument("--top", type=int, default=12); s.set_defaults(fn=cmd_pixel)
    s = sub.add_parser("erase", help="gomme : sk erase ID x,y,w,h [#RRGGBB ...] [--tol N] [--fill clear|near|16x16] "
                                     "(texte collé, tracés ; sans couleur = tout le rectangle)")
    s.add_argument("id"); s.add_argument("box"); s.add_argument("colors", nargs="*")
    s.add_argument("--tol", type=int, default=0); s.add_argument("--fill", default="clear"); s.set_defaults(fn=cmd_erase)
    s = sub.add_parser("flood", help="rend transparente la région connexe de la couleur du point : sk flood ID x,y [--tol N]")
    s.add_argument("id"); s.add_argument("point"); s.add_argument("--tol", type=int, default=0)
    s.add_argument("--max", type=int, default=200000); s.set_defaults(fn=cmd_flood)
    s = sub.add_parser("name", help="nommer un item ou une entité : sk name ID e3 old_man")
    s.add_argument("id"); s.add_argument("ref"); s.add_argument("name"); s.set_defaults(fn=cmd_name)
    s = sub.add_parser("zone", help="zone avec ses propres réglages : sk zone ID x,y,w,h layout=grid grid_pitch=16x32 frames=9 | "
                                    "sk zone ID x,y,w,h skip | sk zone ID list | sk zone ID del N")
    s.add_argument("id"); s.add_argument("box"); s.add_argument("pairs", nargs="*"); s.set_defaults(fn=cmd_zone)
    s = sub.add_parser("autovalidate", help="feuilles todo sans anomalie -> auto_ok (marquées NON vérifiées)")
    s.add_argument("--sample", type=float, default=0.1, help="part des auto_ok renvoyée en relecture agent")
    s.add_argument("--dry", action="store_true"); s.set_defaults(fn=cmd_autovalidate)
    s = sub.add_parser("suggest", help="réglages des feuilles sœurs validées : sk suggest ID [--apply]")
    s.add_argument("id"); s.add_argument("--apply", action="store_true"); s.set_defaults(fn=cmd_suggest)
    sub.add_parser("dupes", help="marque les doublons et miroirs entre toutes les feuilles et tous les jeux").set_defaults(fn=cmd_dupes)
    s = sub.add_parser("journal", help="historique : sk journal [ID] [--last N]")
    s.add_argument("id", nargs="?"); s.add_argument("--last", type=int, default=40); s.set_defaults(fn=cmd_journal)
    s = sub.add_parser("clear", help="efface des corrections : drop|keep|merge|split|add|carve|cut|names|setnames|setbox|entities|erase|flood|anims|all")
    s.add_argument("id"); s.add_argument("what"); s.set_defaults(fn=cmd_clear)
    s = sub.add_parser("region", help="cartes/tilesets : sk region ID zN skip|unskip|offset=ox,oy|auto")
    s.add_argument("id"); s.add_argument("zone"); s.add_argument("action"); s.set_defaults(fn=cmd_region)
    s = sub.add_parser("gridcheck", help="cartes : compare les meilleurs décalages de grille d'une zone : sk gridcheck ID zN")
    s.add_argument("id"); s.add_argument("zone"); s.set_defaults(fn=cmd_gridcheck)
    s = sub.add_parser("recon", help="cartes : vérifie la reconstruction d'une feuille et confirme l'étape si >= 97 %%")
    s.add_argument("id"); s.set_defaults(fn=cmd_recon)
    s = sub.add_parser("tiles", help="construit la bibliothèque de tuiles d'un jeu : sk tiles emerald")
    s.add_argument("game"); s.set_defaults(fn=cmd_tiles)
    s = sub.add_parser("objects", help="objets des cartes d'un jeu (maisons, meubles...) + planches : sk objects emerald")
    s.add_argument("game"); s.set_defaults(fn=cmd_objects)
    s = sub.add_parser("objdrop", help="jeter des objets d'une page : sk objdrop obj_emerald_03 4 12 (numéros #N de la planche)")
    s.add_argument("id"); s.add_argument("refs", nargs="+"); s.add_argument("--undo", action="store_true")
    s.set_defaults(fn=cmd_objdrop)
    s = sub.add_parser("objname", help="nommer un objet : sk objname obj_emerald_03 7 red_roof_house")
    s.add_argument("id"); s.add_argument("ref"); s.add_argument("name"); s.set_defaults(fn=cmd_objname)
    s = sub.add_parser("objsplit", help="découper un objet collé : sk objsplit obj_emerald_03 7 0,1,2,2 (rectangles EN TUILES "
                                        "x,y,l,h dans l'objet ; le reste forme d'autres morceaux) | undo")
    s.add_argument("id"); s.add_argument("ref"); s.add_argument("rects", nargs="+"); s.set_defaults(fn=cmd_objsplit)
    s = sub.add_parser("setname", help="nomme un ensemble (légende) : sk setname ID S3 fire_blast (none = pas un ensemble)")
    s.add_argument("id"); s.add_argument("ref"); s.add_argument("name"); s.set_defaults(fn=cmd_setname)
    s = sub.add_parser("setbox", help="rattache à l'ensemble Sn tous les sprites d'une boîte : sk setbox ID S2 x,y,w,h")
    s.add_argument("id"); s.add_argument("ref"); s.add_argument("box"); s.set_defaults(fn=cmd_setbox)
    s = sub.add_parser("entity", help="ces items (dans cet ordre) forment UNE animation : sk entity ID 12 13 14 15")
    s.add_argument("id"); s.add_argument("refs", nargs="+"); s.set_defaults(fn=cmd_entity)
    s = sub.add_parser("slice", help="coupe l'item n en parts égales : sk slice ID n COLS [ROWS] (sprites collés)")
    s.add_argument("id"); s.add_argument("ref"); s.add_argument("cols", type=int)
    s.add_argument("rows", type=int, nargs="?", default=1); s.set_defaults(fn=cmd_slice)
    s = sub.add_parser("tdrop", help="bords de terrains : jeter de faux bords : sk tdrop tp_emerald_03 4 9 [--undo]")
    s.add_argument("id"); s.add_argument("refs", nargs="+"); s.add_argument("--undo", action="store_true"); s.set_defaults(fn=cmd_tdrop)
    s = sub.add_parser("tname", help="bords de terrains : nommer un terrain : sk tname tp_emerald_03 12 sand")
    s.add_argument("id"); s.add_argument("terrain"); s.add_argument("name"); s.set_defaults(fn=cmd_tname)
    s = sub.add_parser("anims", help="animations nommées d'une entité : sk anims ID e3 walk_down=3,0,4,0 walk_up=5,1,6,1 "
                                     "walk_left=7,2,8,2 idle_down=0 (n° de frame dans l'entité)")
    s.add_argument("id"); s.add_argument("ref"); s.add_argument("spec", nargs="+"); s.set_defaults(fn=cmd_anims)
    s = sub.add_parser("captions", help="planche légende -> animation, pour nommer les entités : sk captions ID")
    s.add_argument("id"); s.set_defaults(fn=cmd_captions)
    s = sub.add_parser("regress", help="après une modif de l'outil : feuilles validées dont la sortie change -> relecture")
    s.add_argument("--write", action="store_true", help="régénérer aussi les fichiers des feuilles inchangées")
    s.set_defaults(fn=cmd_regress)
    s = sub.add_parser("check", help="confirme une étape : sk check ID decoupage|regroupement|nommage|grille|reconstruction ok|na \"note\"")
    s.add_argument("id"); s.add_argument("stage"); s.add_argument("result", choices=["ok", "na"])
    s.add_argument("note", nargs="?"); s.set_defaults(fn=cmd_check)
    s = sub.add_parser("coverage", help="étapes confirmées / à faire, par type : sk coverage [--game G] [--list]")
    s.add_argument("--game"); s.add_argument("--list", action="store_true"); s.set_defaults(fn=cmd_coverage)
    s = sub.add_parser("audit", help="fiabilité des agents : sk audit --n 10 (feuilles ok de Haiku -> relecture Gemini) | --report")
    s.add_argument("--n", type=int, default=10); s.add_argument("--type"); s.add_argument("--seed", type=int, default=1)
    s.add_argument("--report", action="store_true"); s.set_defaults(fn=cmd_audit)
    sub.add_parser("godot", help="catalogue pour Godot (entités animées, objets, terrains) : rpg/godot/catalog.json"
                   ).set_defaults(fn=cmd_godot)
    sub.add_parser("report", help="récapitulatif : avancement, qui a fait quoi, temps, consommation, reste à faire"
                   ).set_defaults(fn=cmd_report)
    s = sub.add_parser("status", help=f"change le statut : {config.STATUSES}")
    s.add_argument("id"); s.add_argument("status"); s.add_argument("note", nargs="?"); s.set_defaults(fn=cmd_status)

    args = p.parse_args(argv)
    _guard(args)
    args.fn(args)
    if args.cmd in MUTATING:
        sid = getattr(args, "id", None) or getattr(args, "game", None)
        detail = {k: v for k, v in vars(args).items() if k not in ("fn", "cmd", "id") and v not in (None, False, [])}
        journal.log(args.cmd, sid, **detail)


if __name__ == "__main__":
    main()
