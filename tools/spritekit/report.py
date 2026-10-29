"""Récapitulatif : ce qui est fait (par qui), ce qui reste, % d'avancement, temps et consommation.

Sources : fiches (statuts, confirmations d'étapes et leur auteur `by`), journaux d'agents
(rpg/pipeline/logs/*.log : modèle, feuilles, durée, coût Claude Code), journal.jsonl, et les transcripts
Claude Code du projet (~/.claude/projects/...) pour les tokens par modèle.
Les estimations du reste sont des moyennes observées : grossières, à lire comme des ordres de grandeur.
"""
import glob
import json
import os
import re
import time
from collections import Counter, defaultdict

from . import checks, config

LOGS = os.path.join(config.PIPELINE, "logs")
TRANSCRIPTS = os.path.expanduser("~/.claude/projects/-home-garen-games")
LOT_RE = re.compile(r"^# lot (\S+) : (\[.*\])\n# modèle (\S+)", re.M)
# hypothèses quand rien n'a encore été mesuré (cartes : jamais déléguées)
GUESS = {"map_factor": 1.5, "escalade_part": 0.2}


def _family(model):
    m = re.sub(r"-(low|medium|high|xhigh|max)$", "", model.split(":", 1)[-1])
    return {"claude-haiku-5-5": "Haiku 5.5", "gemini-3.8-flash": "Gemini 3.8 Flash", "gemini-4-argon": "Gemini 4 Argon",
            "claude-sonnet-5-5": "Sonnet 5.5", "claude-opus-5-5": "Opus 5.5"}.get(m, m)


def lots():
    """Un enregistrement par lot d'agent : modèle, feuilles, durée (s), coût (USD, Claude Code seulement)."""
    from delegate import tool_usage  # noqa: PLC0415  (tools/ est dans le chemin quand on lance sk)
    out = []
    for f in sorted(glob.glob(os.path.join(LOGS, "*.log"))):
        with open(f, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        m = LOT_RE.search(text)
        if not m:
            continue
        tag, ids, model = m.group(1), json.loads(m.group(2).replace("'", '"')), m.group(3)
        try:
            t0 = time.mktime(time.strptime(tag[:15], "%Y%m%d_%H%M%S"))
            dur = max(0, os.path.getmtime(f) - t0)
        except ValueError:
            dur = None
        u = tool_usage(text) or {}
        out.append({"lot": tag, "model": _family(model), "ids": ids, "dur": dur,
                    "usd": u.get("cout_usd"), "tokens": u.get("tokens")})
    return out


def transcript_tokens():
    """Tokens par modèle dans les transcripts Claude Code du projet (session principale + agents claude -p)."""
    tot = defaultdict(Counter)
    sessions = defaultdict(set)
    for f in glob.glob(os.path.join(TRANSCRIPTS, "*.jsonl")):
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"usage"' not in line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = e.get("message")
                if e.get("type") != "assistant" or not isinstance(msg, dict) or not msg.get("usage"):
                    continue
                mod, u = _family(msg.get("model", "?")), msg["usage"]
                sessions[mod].add(os.path.basename(f))
                tot[mod]["sortie"] += u.get("output_tokens", 0) or 0
                tot[mod]["entrée"] += (u.get("input_tokens", 0) or 0) + (u.get("cache_creation_input_tokens", 0) or 0)
                tot[mod]["cache lu"] += u.get("cache_read_input_tokens", 0) or 0
    return tot, {k: len(v) for k, v in sessions.items()}


def _who(by):
    """Auteur d'une confirmation -> libellé lisible."""
    if not by:
        return "?"
    if by == "outil":
        return "outil (automatique)"
    if by == "manuel":
        return "manuel (Claude / toi via sk)"
    if by.startswith("historique:"):
        return "rétroactif (" + _who(by.split(":", 1)[1]) + ")"
    if by.startswith("cc:"):
        return "Haiku 5.5" if "haiku" in by else "Claude Code (" + by[3:] + ")"
    if by.startswith("agy"):
        if "argon" in by:
            return "Gemini 4 Argon"
        return "Gemini (agy)"
    return by


def _pct(a, b):
    return f"{100 * a / b:5.1f} %" if b else "  —  "


def _h(sec):
    sec = int(sec or 0)
    return f"{sec // 3600}h{sec % 3600 // 60:02d}"


def build():
    sheets = list(config.all_sheets())
    lines = []
    w = lines.append
    w(f"RÉCAPITULATIF — {time.strftime('%Y-%m-%d %H:%M')}")
    w("=" * 78)

    # ------------------------------------------------------------------ avancement
    w("\n1. AVANCEMENT (feuilles)")
    groups = {"Sprites / persos / effets": ("sprites", "characters"), "Cartes / tilesets": ("map", "tileset"),
              "Pages d'objets des cartes": ("objects",), "Tables de terrains PMD": ("terrainset",)}
    remaining = {}
    for label, types in groups.items():
        cs = [c for c in sheets if c["type"] in types]
        st = Counter(c["status"] for c in cs)
        n = len(cs) - st["skip"]
        done = sum(1 for c in cs if c["status"] == "ok" and not checks.missing(c))
        w(f"\n  {label} : {n} à traiter (+{st['skip']} ignorées)")
        w(f"    vérifiées (ok, toutes étapes)  {done:4d}  {_pct(done, n)}")
        if st["auto_ok"]:
            w(f"    validées auto, NON vérifiées   {st['auto_ok']:4d}  {_pct(st['auto_ok'], n)}")
        for s_ in ("needs_review", "todo", "extracted", "needs_fix"):
            if st[s_]:
                w(f"    {s_:<31}{st[s_]:4d}  {_pct(st[s_], n)}")
        esc = Counter(c.get("level", 0) for c in cs if c["status"] not in ("ok", "skip", "auto_ok"))
        if any(k > 0 for k in esc):
            w("    en file par niveau d'escalade : " + ", ".join(f"niveau {k} : {v}" for k, v in sorted(esc.items())))
        # étapes
        stages = checks.STAGES[types[0]]
        for stg in stages:
            ok = sum(1 for c in cs if c["status"] != "skip" and stg in c.get("checks", {})
                     and stg not in [m[0] for m in checks.missing(c)])
            w(f"    étape {stg:<25}{ok:4d}  {_pct(ok, n)} confirmée(s)")
        remaining[types[0]] = [c for c in cs if c["status"] not in ("ok", "skip")]

    # ------------------------------------------------------------------ qui
    w("\n2. QUI A FAIT QUOI")
    by_stage = defaultdict(Counter)
    for c in sheets:
        for stg, ch in c.get("checks", {}).items():
            by_stage[_who(ch.get("by"))][stg] += 1
    w("  Confirmations d'étapes actuellement enregistrées, par auteur :")
    for who, cnt in sorted(by_stage.items(), key=lambda kv: -sum(kv[1].values())):
        w(f"    {who:<38}{sum(cnt.values()):4d}  ({', '.join(f'{k} {v}' for k, v in cnt.most_common())})")
    final = Counter()
    for c in sheets:
        if c["status"] in ("ok", "needs_fix"):
            bys = [ch.get("by", "") for ch in c.get("checks", {}).values()]
            final[(_who(Counter(bys).most_common(1)[0][0]) if bys else "aucune étape confirmée", c["status"])] += 1
    w("  Statut final, par auteur principal des confirmations :")
    for (who, stt), v in sorted(final.items(), key=lambda kv: -kv[1]):
        w(f"    {who:<38}{stt:<10}{v:4d}")

    w("  Avant le système de confirmations (27/10, 20h) : Gemini 3.8 Flash (agy) a fait le premier découpage de la")
    w("  plupart des feuilles ; ses validations ont été remises en relecture à la migration, puis confirmées par Haiku.")

    # ------------------------------------------------------------------ temps / conso
    w("\n3. TEMPS ET CONSOMMATION")
    L = lots()
    per = defaultdict(lambda: {"lots": 0, "feuilles": 0, "dur": 0.0, "usd": 0.0, "tokens": 0})
    for lt in L:
        p = per[lt["model"]]
        p["lots"] += 1
        p["feuilles"] += len(lt["ids"])
        p["dur"] += lt["dur"] or 0
        p["usd"] += lt["usd"] or 0
        p["tokens"] += lt["tokens"] or 0
    w("  Agents délégués (journaux rpg/pipeline/logs) :")
    w(f"    {'modèle':<20}{'lots':>5}{'feuilles':>10}{'temps agent':>13}{'min/feuille':>13}{'coût':>11}")
    for mod, p in per.items():
        mpf = p["dur"] / 60 / p["feuilles"] if p["feuilles"] else 0
        cost = f"{p['usd']:.2f} $" if p["usd"] else "n.c."
        w(f"    {mod:<20}{p['lots']:>5}{p['feuilles']:>10}{_h(p['dur']):>13}{mpf:>12.1f}m{cost:>11}")
    w("    (feuilles = attributions, une feuille reprise compte plusieurs fois ; « n.c. » : agy ne donne pas "
      "sa consommation, quota Google séparé)")
    tok, ses = transcript_tokens()
    w("  Tokens Claude (transcripts du projet ; quota Claude partagé entre ces modèles) :")
    for mod, t in sorted(tok.items(), key=lambda kv: -kv[1]["sortie"]):
        w(f"    {mod:<20}{ses.get(mod, 0):>4} session(s)  sortie {t['sortie'] / 1e6:6.2f} M   entrée {t['entrée'] / 1e6:6.2f} M"
          f"   cache lu {t['cache lu'] / 1e6:7.1f} M")
    w("    ($ = valeur affichée par Claude Code pour les agents, en équivalent API ; sur abonnement, c'est du quota)")
    w("    (Opus 5.5 = la session principale : outils, doc, revues ; le coût en $ n'est connu que pour les agents "
      "Haiku, d'après Claude Code)")

    # ------------------------------------------------------------------ reste
    w("\n4. RESTE À FAIRE (estimations)")
    hk = per.get("Haiku 5.5")
    gm = per.get("Gemini 3.8 Flash")
    h_min = hk["dur"] / 60 / hk["feuilles"] if hk and hk["feuilles"] else 7.0
    h_usd = hk["usd"] / hk["feuilles"] if hk and hk["feuilles"] else 0.3
    g_min = gm["dur"] / 60 / gm["feuilles"] if gm and gm["feuilles"] else 7.0
    sp = remaining["sprites"]
    hard = [c for c in sp if c["status"] == "needs_fix" or c.get("level", 0) > 0]
    easy = [c for c in sp if c not in hard]
    mp = remaining["map"]
    e = GUESS["escalade_part"]
    mf = GUESS["map_factor"]
    rows = [
        ("Sprites à relire (Haiku)", len(easy), len(easy) * h_min, len(easy) * h_usd, len(easy) * e * g_min),
        ("Sprites difficiles (Gemini)", len(hard), 0, 0, len(hard) * g_min * 1.5),
        ("Cartes (Haiku, hypothèse)", len(mp), len(mp) * h_min * mf, len(mp) * h_usd * mf, len(mp) * e * g_min),
    ]
    w(f"    {'chantier':<30}{'feuilles':>9}{'Haiku':>9}{'≈ $':>9}{'Gemini':>9}")
    for name, n, hm, usd, gmn in rows:
        w(f"    {name:<30}{n:>9}{_h(hm * 60):>9}{usd:>8.1f}${_h(gmn * 60):>9}")
    th = sum(r[2] for r in rows) / 4
    tg = sum(r[4] for r in rows) / 2
    w(f"    Durée murale avec 4 Haiku + 2 Gemini en parallèle : ≈ {_h(max(th, tg) * 60)} (hors attentes de quota)")
    w(f"    Bases : Haiku {h_min:.1f} min et {h_usd:.2f} $ par feuille (mesuré) ; Gemini {g_min:.1f} min (mesuré) ;"
      f" cartes = Haiku x{mf} (hypothèse : jamais déléguées) ; {int(e * 100)} % escaladées (hypothèse).")
    w("  Chantiers hors feuilles (non chiffrés, à faire par Claude) :")
    for t in ("bords de terrains Pokémon / Minish (autotiles) : données expérimentales, à vérifier (docs/godot.md)",
              "Godot : régénérer après les vérifications (sk godot + build_resources.gd) ; collisions = heuristique",
              "revue hostile : points restants dans docs/limites-et-reste-a-faire.md"):
        w("    - " + t)
    return "\n".join(lines)
