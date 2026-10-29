#!/usr/bin/env python3
"""
Répartit la vérification des feuilles entre des agents, sur une RÉSERVE de modèles et de moteurs :
- `cc:` Claude Code non interactif (`claude -p`, outils limités à tools/sk + Read), ex. cc:claude-haiku-5-5 ;
- `agy:` Antigravity (Gemini Flash / Argon, Claude, GPT-OSS ont chacun leur quota) — DÉSACTIVÉ par défaut.
Les familles sont utilisées en même temps, chacune avec son nombre de places ; une famille épuisée se
met en pause sans arrêter les autres.

Exemples :
  tools/delegate.py --status todo,needs_review --wait-quota                 # 4 agents Haiku 5.5
  tools/delegate.py --pool "cc:claude-haiku-5-5:4,cc:claude-sonnet-5-5:1"
  tools/delegate.py --allow-agy --pool "agy:gemini-3.8-flash-high:3,cc:claude-haiku-5-5:4"
  tools/delegate.py --ids 8329 26917 --model claude-haiku-5-5 --parallel 1

Chaque agent reçoit un lot de feuilles et le guide tools/AGENT_GUIDE.md. Journaux : rpg/pipeline/logs/,
historique : rpg/pipeline/journal.jsonl (tools/sk journal). Voir docs/delegation.md.

Sécurités :
  - quota détecté dans la sortie d'agy -> la FAMILLE du modèle est mise en pause jusqu'à la remise à zéro
    annoncée (+5 min) ; lots « suspects » (fini en < --min-seconds sans conclusion) répétés -> pause aussi ;
    alerte dans rpg/pipeline/ALERT.txt + notification de bureau ;
  - toutes les familles en pause : attente (--wait-quota) ou sortie avec le code 2 ;
  - fichier rpg/pipeline/STOP -> arrêt propre (les agents en cours finissent, aucun nouveau lot) ;
  - les places tiennent compte des agents agy déjà actifs, modèle par modèle (relance sans doublon).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spritekit import auto, config, journal  # noqa: E402

GAMES_DIR = os.path.dirname(config.PROJECT)
LOGS = os.path.join(config.PIPELINE, "logs")
ALERT = os.path.join(config.PIPELINE, "ALERT.txt")
STOP = os.path.join(config.PIPELINE, "STOP")
DONE = {"ok", "needs_fix", "skip", "auto_ok"}
RESET_RE = re.compile(r"resets? in\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?", re.I)
RESET_AT_RE = re.compile(r"reset(?:s)?\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.I)  # Claude Code


def reset_seconds(text):
    """Délai avant remise à zéro du quota, d'après le message du moteur (None si inconnu)."""
    m = RESET_RE.search(text)
    if m and any(m.groups()):
        h_, m_, s_ = (int(g) if g else 0 for g in m.groups())
        return h_ * 3600 + m_ * 60 + s_
    m = RESET_AT_RE.search(text)
    if m:
        hh, mm, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
        if ap == "pm" and hh < 12:
            hh += 12
        if ap == "am" and hh == 12:
            hh = 0
        now = time.localtime()
        target = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, hh, mm, 0, 0, 0, -1))
        if target <= time.time():
            target += 86400
        return int(target - time.time())
    return None
QUOTA_RE = re.compile(r"quota|rate.?limit|\b429\b|resource.?exhausted|usage limit|limit (?:reached|exceeded)|"
                      r"too many requests|out of credits|insufficient credit|billing", re.I)

PROMPT_MAP = """Tu es un agent de vérification de cartes en tuiles.
Lis d'abord entièrement le fichier tools/AGENT_GUIDE.md (dans {root}), surtout la section « Feuilles de CARTES ».
Feuilles qui te sont assignées (dans cet ordre) : {ids}.
Pour chacune : `tools/sk run ID`, regarde rpg/pipeline/qa/ID/regions_*.png, corrige les zones (gridcheck,
region), `tools/sk recon ID`, confirme les étapes (`tools/sk check ID grille ok|na "note"`, et reconstruction
si sk recon ne l'a pas fait), puis `tools/sk status ID ok|needs_fix|skip "note"`.
N'utilise que tools/sk. Termine par un résumé d'une ligne par feuille.{resume}"""

PROMPT_OBJ = """Tu es un agent de vérification d'objets de décor extraits des cartes.
Lis d'abord entièrement le fichier tools/AGENT_GUIDE.md (dans {root}), surtout la section « Pages d'OBJETS ».
Pages qui te sont assignées (dans cet ordre) : {ids}.
Pour chacune : `tools/sk run ID`, regarde CHAQUE planche rpg/pipeline/qa/ID/objets_*.png, jette / découpe / nomme
(objdrop, objsplit, objname), relance `tools/sk run ID`, puis `tools/sk check ID objets ok "note"` et
`tools/sk status ID ok|needs_fix "note"`. N'utilise que tools/sk. Termine par un résumé d'une ligne par page.{resume}"""

PROMPT_TERRAIN = """Tu es un agent de vérification de tables d'autotiles (Donjon Mystère).
Lis d'abord entièrement le fichier tools/AGENT_GUIDE.md (dans {root}), surtout la section « Tables de TERRAINS ».
Feuilles qui te sont assignées (dans cet ordre) : {ids}.
Pour chacune : `tools/sk run ID`, regarde rpg/pipeline/qa/ID/terrains_*.png, corrige les noms des groupes si
besoin (`tools/sk set ID pmd_groups='[...]'` puis `tools/sk run ID`), puis `tools/sk check ID terrains ok "note"`
et `tools/sk status ID ok|needs_fix "note"`. N'utilise que tools/sk. Termine par un résumé d'une ligne par feuille.{resume}"""

PROMPT_TP = """Tu es un agent de vérification de bords de terrains (tuiles de transition entre deux sols).
Lis d'abord entièrement le fichier tools/AGENT_GUIDE.md (dans {root}), surtout la section « Pages de BORDS de terrains ».
Pages qui te sont assignées (dans cet ordre) : {ids}.
Pour chacune : `tools/sk run ID`, regarde rpg/pipeline/qa/ID/bords_0.png, jette les faux bords (`tools/sk tdrop ID n...`),
nomme les terrains (`tools/sk tname ID id nom`), `tools/sk run ID`, puis `tools/sk check ID bords ok "note"` et
`tools/sk status ID ok|needs_fix "note"`. N'utilise que tools/sk. Termine par un résumé d'une ligne par page.{resume}"""

PROMPT = """Tu es un agent de vérification de découpage de sprites.
Lis d'abord entièrement le fichier tools/AGENT_GUIDE.md (dans {root}) et applique sa méthode.
Feuilles qui te sont assignées (dans cet ordre) : {ids}.
Pour chacune : lance `tools/sk run ID`, regarde le rapport ET les images de rpg/pipeline/qa/ID/,
corrige avec les commandes tools/sk, confirme les étapes obligatoires (decoupage, regroupement, nommage)
avec `tools/sk check ID ETAPE ok|na "note"`, puis termine par `tools/sk status ID ok|needs_fix|skip "note"`.
N'utilise que tools/sk. Termine par un résumé d'une ligne par feuille.{resume}"""

RESUME = """

ATTENTION, reprise : ces feuilles ont déjà été commencées par un agent précédent qui s'est arrêté avant
de conclure. Leurs corrections sont DÉJÀ enregistrées dans leur fiche (tools/sk show ID) et leur historique
est dans `tools/sk journal ID`. Ne recommence pas de zéro : lance `tools/sk run ID`, regarde où en est le
résultat, termine ce qui manque et conclus avec un statut.
{details}"""


def engine_text(text):
    """Revue I3 : en stream-json, seuls les événements du moteur (result, system, erreurs) parlent de quota ;
    les sorties de sk (coordonnées « 429 », journal « quota ») ne doivent pas couper une famille."""
    out = []
    for line in text.splitlines():
        ls = line.strip()
        if not ls.startswith("{"):
            out.append(line)
            continue
        try:
            ev = json.loads(ls)
        except ValueError:
            out.append(line)
            continue
        if ev.get("type") in ("result", "system", "error") or ev.get("is_error"):
            out.append(json.dumps({k: ev.get(k) for k in ("type", "subtype", "result", "error", "is_error")}))
    return "\n".join(out)


def resume_text(ids):
    lines = []
    for i in ids:
        c = config.load(i)
        if not c.get("resume"):
            continue
        ov = {k: len(v) for k, v in c.get("overrides", {}).items() if v}
        note = c.get("notes", "").strip().splitlines()[-1:] or [""]
        esc = c.get("escalations", [])
        if esc:
            lines.append(f"- {i} : le modèle précédent ({esc[-1]['modele']}) n'y est pas arrivé : {esc[-1]['raison'][:400]}\n"
                         "  Tu as une meilleure vision : regarde attentivement les planches (sk zoom) et va au bout "
                         "(commandes à la main au besoin). `tools/sk show ID` pour tout le diagnostic.")
        lines.append(f"- {i} : tentative {c.get('attempts', 0) + 1}, réglages {json.dumps(c.get('params', {}), ensure_ascii=False)}, "
                     f"corrections {json.dumps(ov)}, zones {len(c.get('zones', []))}\n  dernière note : {note[0][:500]}")
    return RESUME.format(details="\n".join(lines)) if lines else ""


# Moteurs : "cc" = Claude Code en mode non interactif (claude -p), "agy" = Antigravity.
# agy est DÉSACTIVÉ par défaut (plus de quota, 2026-10-27) : il faut --allow-agy pour l'utiliser.
DEFAULT_POOL = "cc:claude-haiku-5-5:4"
# Escalade (2026-10-28) : Haiku fait tout d'abord ; une feuille où il « galère » monte au niveau suivant
# (Gemini, meilleure vision), puis au dernier (Gemini Argon) ; échec au dernier niveau -> needs_fix (développeur).
ESCALADE_POOL = "cc:claude-haiku-5-5:4@0,agy:gemini-3.8-flash-high:2@1,agy:gemini-4-argon-high:1@2"
POOL_PRESETS = {"escalade": ESCALADE_POOL}
# niveau par défaut d'une famille de modèles (surcharge : « modèle:places@niveau » dans --pool)
LEVELS = {"cc:claude-haiku-5-5": 0, "agy:gemini-3.8-flash": 1, "agy:gemini-4-argon": 2,
          "agy:claude-sonnet-5-5": 2, "cc:claude-sonnet-5-5": 2, "agy:claude-opus-5-5": 2, "cc:claude-opus-5-5": 2}
MAX_LEVEL = 2
POOL_LEVELS = {}  # rempli par parse_pool
AGY_POOL_EXAMPLE = "agy:gemini-3.8-flash-high:3,agy:gemini-4-argon-high:2,agy:claude-sonnet-5-5-high:2"
EFFORT_RE = re.compile(r"-(low|medium|high|xhigh|max)$")


def family(model):
    """Famille de quota : moteur + modèle sans niveau d'effort (agy:gemini-4-argon-high -> agy:gemini-4-argon)."""
    return EFFORT_RE.sub("", model)


def level_of(model):
    return POOL_LEVELS.get(model, LEVELS.get(family(model), 0))


def target_level(c, levels):
    """Niveau de la réserve qui prend cette feuille : le plus bas >= niveau de la feuille (None : personne)."""
    ok = [lv for lv in levels if lv >= c.get("level", 0)]
    return min(ok) if ok else None


POOL_TOP = [MAX_LEVEL]  # niveau le plus haut de la réserve du lancement (fixé dans main)
ACTIVE = set()          # lots gérés par CE répartiteur dans un thread (release_stale ne les touche pas)
BACKUP_LOCK = threading.Lock()


def backup(msg):
    """Sauvegarde git des fiches (rpg/pipeline) après chaque lot : un agent qui casse tout est rattrapable."""
    import subprocess
    repo = os.path.join(GAMES_DIR, "rpg", "pipeline")
    if not os.path.isdir(os.path.join(repo, ".git")):
        return
    with BACKUP_LOCK:
        subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True)
        subprocess.run(["git", "-c", "user.name=delegate", "-c", "user.email=delegate@local", "commit", "-qm", msg],
                       cwd=repo, capture_output=True)


def escalate(c, tag, model, before, reason):
    """La feuille passe au niveau au-dessus : statut de travail, tentatives remises à zéro, reprise."""
    c["level"] = level_of(model) + 1
    c["status"] = before if before in ("todo", "needs_review") else "needs_review"
    c["attempts"] = 0
    c["resume"] = True
    c.setdefault("escalations", []).append({"lot": tag, "modele": model, "raison": reason,
                                            "t": time.strftime("%Y-%m-%d %H:%M:%S")})
    c["notes"] = (c.get("notes", "") + f"\n[{tag}] ESCALADE niveau {c['level']} : {reason}").strip()
    # revue hostile I2 : le niveau au-dessus refait TOUTES les confirmations (sinon il peut remettre ok
    # sur des étapes confirmées par l'agent qui a échoué)
    if c.get("checks"):
        c.setdefault("checks_history", []).append({"lot": tag, "checks": c.pop("checks")})
    if c["type"] not in ("objects",):
        try:
            auto.refresh_marker(c)
        except Exception:
            pass
    journal.log("escalade", c["id"], lot=tag, modele=model, niveau=c["level"], raison=reason)


def split_model(model):
    backend, _, name = model.partition(":")
    return (backend, name) if backend in ("cc", "agy") else ("agy", model)


def agent_cmd(model, prompt, timeout):
    backend, name = split_model(model)
    if backend == "cc":
        # outils limités au strict nécessaire : tools/sk et la lecture des planches
        # stream-json : chaque appel d'outil est journalisé (on vérifie que l'agent regarde les planches)
        return ["claude", "-p", prompt, "--model", name, "--allowedTools", "Bash(tools/sk:*)", "Read",
                "--output-format", "stream-json", "--verbose"]
    return ["agy", "-p", prompt, "--model", name, "--dangerously-skip-permissions", "--print-timeout", f"{timeout}s"]


def alert(msg, title="Délégation agy", urgent=True):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    with open(ALERT, "a", encoding="utf-8") as f:
        f.write(line)
    print("!!! " + line, end="", flush=True)
    try:
        subprocess.run(["notify-send"] + (["-u", "critical"] if urgent else []) + [title, msg], timeout=5)
    except Exception:  # noqa: BLE001
        pass


class Breaker:
    """Disjoncteur d'une famille de modèles (partagé entre les threads)."""

    def __init__(self, fam, max_suspect):
        self.fam = fam
        self.lock = threading.Lock()
        self.tripped = None       # raison
        self.until = None         # horodatage de reprise (None = jusqu'à la fin de ce lancement)
        self.suspect_streak = 0
        self.max_suspect = max_suspect

    def blocked(self):
        with self.lock:
            if self.tripped and self.until is not None and time.time() >= self.until:
                self.tripped, self.until, self.suspect_streak = None, None, 0
                print(f"reprise de la famille {self.fam}", flush=True)
            return self.tripped is not None

    def trip(self, reason, reset_in=None):
        with self.lock:
            if self.tripped:
                return
            self.tripped = reason
            # revue I3 : sans heure de remise à zéro connue, pause de 30 min (plus jusqu'à la fin du lancement)
            self.until = time.time() + (reset_in + 300 if reset_in else 1800)
            until = time.strftime("%H:%M", time.localtime(self.until)) if self.until else "fin du lancement"
        alert(f"famille {self.fam} en pause jusqu'à {until} : {reason}")

    def record(self, suspect, reason):
        with self.lock:
            self.suspect_streak = self.suspect_streak + 1 if suspect else 0
            streak = self.suspect_streak
        if suspect and streak >= self.max_suspect:
            self.trip(f"{streak} lots suspects d'affilée ({reason})", 1800)


def running_agents(model=None):
    """Lignes de commande des agents actifs (agy ou claude, lancés par ce script ou un précédent),
    éventuellement seulement ceux d'un modèle donné ("cc:claude-haiku-5-5", "agy:gemini-...")."""
    lines = []
    for pat in ("agy -p", "claude -p"):
        try:
            out = subprocess.run(["pgrep", "-af", pat], capture_output=True, text=True).stdout
        except FileNotFoundError:
            continue
        lines += [l for l in out.splitlines() if "AGENT_GUIDE" in l and len(l.split(None, 1)) > 1
                  and not l.split(None, 1)[1].startswith("/bin/")]
    if model:
        backend, name = split_model(model)
        exe = "claude" if backend == "cc" else "agy"
        lines = [l for l in lines if l.split(None, 1)[1].split()[0].endswith(exe)
                 and re.search(rf"--model {re.escape(name)}(\s|$)", l)]
    return lines


def finish_unconcluded(c, tag, reason, count_attempt, max_attempts, before=None):
    """Feuille non conclue : elle retourne dans la file (marquée « à reprendre »), sauf après
    max_attempts tentatives réelles -> needs_fix pour le développeur. Rien n'est perdu : les
    corrections déjà faites sont dans la fiche."""
    if count_attempt:
        c["attempts"] = c.get("attempts", 0) + 1
    if c.get("attempts", 0) >= max_attempts:
        c["status"] = "needs_fix"
        c.pop("resume", None)
        c["notes"] = (c.get("notes", "") + f"\n[{tag}] {c['attempts']} tentatives d'agent sans conclusion ({reason})").strip()
        journal.log("abandon", c["id"], lot=tag, raison=reason, tentatives=c["attempts"])
    else:
        # statut d'avant le lot (needs_review reste needs_review : un répartiteur filtré dessus la reprend)
        c["status"] = before if before in ("todo", "needs_review") else "todo"
        c["resume"] = True
        journal.log("interrompu", c["id"], lot=tag, raison=reason, tentatives=c.get("attempts", 0))


def release_stale(max_attempts=3):
    """Libère les feuilles assignées à un agent qui ne tourne plus (répartiteur tué, plantage...)."""
    live = " ".join(running_agents())
    freed = 0
    for c in config.all_sheets():
        if c.get("assigned") in ACTIVE:
            continue  # revue I4 : lot encore géré par un thread de ce répartiteur
        if c.get("assigned") and f" {c['id']}" not in live and f"{c['id']}." not in live:
            tag = c.pop("assigned")
            if c["status"] not in DONE:
                finish_unconcluded(c, tag, "agent disparu", True, max_attempts)
            config.save(c); freed += 1
    return freed


def pick(args):
    if args.ids:  # revue I12 : jamais une feuille déjà prise par un lot vivant (sauf --reassign)
        return [c for c in (config.load(i) for i in args.ids) if not c.get("assigned") or args.reassign]
    out = []
    for c in config.all_sheets():
        wanted = (("map", "tileset") if args.type in ("map", "tileset") else (args.type,) if args.type in ("objects", "terrainset", "terrainpairs")
                  else ("sprites", "characters"))
        if c["type"] not in wanted:
            continue
        if args.type and c["type"] != args.type and args.type not in ("map", "tileset"): continue
        if args.game and c["game"] not in args.game.split(","): continue
        if args.category and c["category"] != args.category: continue
        if c["status"] not in args.status.split(","): continue
        if c.get("assigned") and not args.reassign: continue
        out.append(c)
    return out  # --limit est un TOTAL par lancement : appliqué dans la boucle principale


def tool_usage(text):
    """Résumé des outils utilisés par un agent Claude Code (sortie stream-json) : planches PNG lues
    (par feuille), commandes sk, texte final. None si la sortie n'est pas du stream-json."""
    pngs, cmds, final, seen = [], [], None, False
    cost, tokens = 0.0, 0
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        seen = True
        if ev.get("type") == "assistant":
            for part in ev.get("message", {}).get("content", []) or []:
                if part.get("type") != "tool_use":
                    continue
                inp = part.get("input", {})
                if part.get("name") == "Read" and str(inp.get("file_path", "")).endswith(".png"):
                    pngs.append(inp["file_path"])
                elif part.get("name") == "Bash":
                    cmds.append(inp.get("command", ""))
        elif ev.get("type") == "result":
            final = ev.get("result")
            mu = ev.get("model_usage_since_last_result") or ev.get("modelUsage") or {}
            if mu:
                for u in mu.values():
                    cost += u.get("costUSD", 0) or 0
                    tokens += sum(u.get(k, 0) or 0 for k in ("inputTokens", "outputTokens",
                                                              "cacheReadInputTokens", "cacheCreationInputTokens"))
            else:
                cost += ev.get("total_cost_usd", 0) or 0
    if not seen:
        return None
    per_sheet = {}
    for f in pngs:
        m = re.search(r"qa/(\w+)/", f)
        if m:
            per_sheet[m.group(1)] = per_sheet.get(m.group(1), 0) + 1
    return {"png_lus": len(pngs), "png_par_feuille": per_sheet, "commandes_sk": len(cmds), "final": final,
            "cout_usd": round(cost, 4), "tokens": tokens}


def assign(batch, model, n):
    """Marque les feuilles comme prises AVANT de lancer le thread (évite qu'un autre lot les reprenne)."""
    ids = [c["id"] for c in batch]
    tag = time.strftime("%Y%m%d_%H%M%S") + f"_b{n}_{family(model).replace(':', '-')}"
    ty = config.load(ids[0])["type"]
    tpl = (PROMPT_MAP if ty in ("map", "tileset") else PROMPT_OBJ if ty == "objects" else PROMPT_TERRAIN
           if ty == "terrainset" else PROMPT_TP if ty == "terrainpairs" else PROMPT)
    before, prompt = {}, tpl.format(root=GAMES_DIR, ids=" ".join(ids), resume=resume_text(ids))
    for i in ids:
        c = config.load(i)
        before[i] = c["status"]
        c["assigned"] = tag
        config.save(c)
        journal.log("attribué", i, lot=tag, modele=model, reprise=bool(c.get("resume")))
    return ids, tag, before, prompt


def run_batch(ids, tag, before, prompt, model, args, breaker):
    ACTIVE.add(tag)
    try:
        return _run_batch(ids, tag, before, prompt, model, args, breaker)
    finally:
        ACTIVE.discard(tag)
        backup(f"lot {tag} : {' '.join(ids)}")


def _run_batch(ids, tag, before, prompt, model, args, breaker):
    log = os.path.join(LOGS, f"{tag}.log")
    cmd = agent_cmd(model, prompt, args.timeout)
    env = dict(os.environ, SK_AGENT=f"{split_model(model)[0]}:{tag}")
    t0 = time.time()
    rc = None
    with open(log, "w", encoding="utf-8") as f:
        f.write(f"# lot {tag} : {ids}\n# modèle {model}\n\n")
        f.flush()
        try:
            rc = subprocess.run(cmd, cwd=GAMES_DIR, stdout=f, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL,
                                timeout=args.timeout + 60).returncode
        except subprocess.TimeoutExpired:
            f.write("\n# TIMEOUT\n")
            rc = "timeout"
    dt = time.time() - t0
    with open(log, encoding="utf-8", errors="replace") as f:
        text = f.read()
    usage = tool_usage(text)
    if usage:
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\n# outils : {usage['png_lus']} planche(s) PNG lue(s) {json.dumps(usage['png_par_feuille'])}, "
                    f"{usage['commandes_sk']} commande(s) sk\n# --- réponse finale ---\n{usage['final'] or ''}\n")
        for i in ids:
            journal.log("outils", i, lot=tag, png_lus=usage["png_par_feuille"].get(i, 0))
    journal.log("lot", None, lot=tag, modele=model, feuilles=ids, duree=int(dt),
                cout_usd=usage.get("cout_usd") if usage else None, tokens=usage.get("tokens") if usage else None)
    # coupure par quota (même en cours de lot) : le message d'agy est explicite
    hit_quota = bool(re.search(r"RESOURCE_EXHAUSTED|quota reached|code 429|usage limit reached|"
                               r"rate limit (?:reached|exceeded)|limit will reset", text, re.I))
    res, concluded = [], 0
    can_escalate = level_of(model) < min(MAX_LEVEL, POOL_TOP[0])  # revue I1 : niveau au-dessus présent ?
    for i in ids:
        c = config.load(i)
        c.pop("assigned", None)
        looked = usage["png_par_feuille"].get(i, 0) if usage else None
        if c["status"] in DONE and not hit_quota:
            concluded += 1
            c.pop("resume", None)
            journal.log("terminé", i, lot=tag, statut=c["status"], duree=int(dt), modele=model)
            if can_escalate and c["status"] == "needs_fix":
                escalate(c, tag, model, before[i], "l'agent n'a pas pu conclure (needs_fix) : "
                         + (c.get("notes", "").strip().splitlines() or [""])[-1][:300])
            elif can_escalate and c["status"] == "ok" and looked == 0:
                escalate(c, tag, model, before[i], "conclue ok sans avoir regardé une seule planche")
            elif can_escalate and c["status"] == "skip" and before[i] != "skip":
                escalate(c, tag, model, before[i], "feuille ignorée (skip) par l'agent : à confirmer par un autre modèle")
        elif c["status"] in DONE:
            concluded += 1
            c.pop("resume", None)
            journal.log("terminé", i, lot=tag, statut=c["status"], duree=int(dt), modele=model)
        elif hit_quota:
            # pas la faute de la feuille : elle retourne dans la file, sans compter de tentative
            finish_unconcluded(c, tag, "quota", False, args.max_attempts, before[i])
        else:
            reason = "timeout" if rc == "timeout" else f"fin sans statut (code {rc})"
            if can_escalate and c.get("attempts", 0) + 1 >= args.escalate_after:
                c["attempts"] = c.get("attempts", 0) + 1
                escalate(c, tag, model, before[i], f"{c['attempts']} tentative(s) sans conclusion ({reason})")
            else:
                finish_unconcluded(c, tag, reason, True, args.max_attempts, before[i])
        config.save(c)
        res.append((i, c["status"]))
    # le texte des agents parle parfois de « limite de l'outil » : hors message d'agy, on ne cherche
    # le quota que si le lot a échoué
    quota = QUOTA_RE.search(engine_text(text)) if (concluded == 0 or hit_quota) else None
    if quota:
        reset = reset_seconds(text)
        breaker.trip(f"quota/limite ({model}) dans {os.path.basename(log)} : « {quota.group(0)} » (code {rc})"
                     + (f", remise à zéro dans {reset // 3600}h{reset % 3600 // 60:02d}" if reset else ""), reset)
    suspect = concluded == 0 and dt < args.min_seconds
    breaker.record(suspect, f"lot {tag} fini en {dt:.0f}s sans conclusion, code {rc}")
    return tag, dt, res, log


def parse_pool(text):
    """ "cc:claude-haiku-5-5:4@0,agy:gemini-3.8-flash-high:3@1" -> [(modèle avec moteur, places)].
    « @N » = niveau d'escalade (défaut : LEVELS). Préréglage : « escalade »."""
    text = POOL_PRESETS.get(text, text)
    pool = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        lv = None
        if "@" in part:
            part, lv = part.rsplit("@", 1)
            lv = int(lv)
        bits = part.split(":")
        n = int(bits[-1]) if len(bits) > 1 and bits[-1].isdigit() else 1
        name = ":".join(bits[:-1]) if len(bits) > 1 and bits[-1].isdigit() else part
        if split_model(name)[0] == "agy" and not name.startswith("agy:"):
            name = "agy:" + name
        pool.append((name, n))
        if lv is not None:
            POOL_LEVELS[name] = lv
    return pool


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ids", nargs="*")
    p.add_argument("--type", choices=["sprites", "characters", "map", "tileset", "objects", "terrainset", "terrainpairs"],
                   help="map / tileset : vérification des cartes (lots homogènes : on ne mélange pas cartes et sprites)")
    p.add_argument("--game", help="jeu(x), séparés par des virgules (ex. emerald,ruby_sapphire,minish_cap)")
    p.add_argument("--category")
    p.add_argument("--status", default="todo", help="statut(s) à traiter, séparés par des virgules (ex. todo,needs_review)")
    p.add_argument("--max-attempts", type=int, default=3, help="tentatives d'agent par feuille avant needs_fix")
    p.add_argument("--escalate-after", type=int, default=2,
                   help="tentatives sans conclusion à un niveau avant de passer au niveau suivant")
    p.add_argument("--batch", type=int, default=3, help="feuilles par agent")
    p.add_argument("--pool", default=DEFAULT_POOL,
                   help="modèles et places : \"modèle:places,modèle:places\" (défaut : %(default)s)")
    p.add_argument("--model", help="raccourci : un seul modèle, ex. claude-haiku-5-5 ou agy:gemini-4-argon-high (avec --parallel)")
    p.add_argument("--parallel", type=int, default=3, help="places pour --model")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--timeout", type=int, default=1800, help="secondes max par agent")
    p.add_argument("--min-seconds", type=int, default=90, help="en dessous, un lot sans conclusion est suspect")
    p.add_argument("--max-suspect", type=int, default=2, help="lots suspects d'affilée avant pause de la famille")
    p.add_argument("--reassign", action="store_true")
    p.add_argument("--allow-agy", action="store_true", help="autoriser le moteur agy (désactivé par défaut)")
    p.add_argument("--wait-quota", action="store_true",
                   help="toutes les familles épuisées : attendre la première remise à zéro au lieu de s'arrêter")
    args = p.parse_args()
    os.environ.setdefault("SK_AGENT", "repartiteur")  # revue I11 : journal signé

    pool = [(args.model if ":" in args.model else f"cc:{args.model}", args.parallel)] if args.model else parse_pool(args.pool)
    if any(split_model(m)[0] == "agy" for m, _ in pool) and not args.allow_agy:
        raise SystemExit("agy est désactivé (plus de quota) : retire-le de --pool ou ajoute --allow-agy")
    os.makedirs(LOGS, exist_ok=True)
    if os.path.exists(STOP):
        print(f"fichier {STOP} présent : supprime-le pour lancer"); return
    freed = release_stale(args.max_attempts)
    if freed:
        print(f"{freed} feuille(s) libérée(s) (agent disparu)")
    breakers = {family(m): Breaker(family(m), args.max_suspect) for m, _ in pool}
    print("réserve : " + ", ".join(f"{m} x{n} (niveau {level_of(m)})" for m, n in pool), flush=True)
    levels = sorted({level_of(m) for m, _ in pool})
    POOL_TOP[0] = max(levels)

    threads = []  # (thread, modèle)
    n_batch = 0
    done_ids = set()
    while not os.path.exists(STOP):
        threads = [(t, m) for t, m in threads if t.is_alive()]
        release_stale(args.max_attempts)
        queue = [c for c in pick(args) if not (args.ids and c["id"] in done_ids)]
        if args.limit:  # bug corrigé 2026-10-28 : la limite était appliquée à chaque tour (pilote non borné)
            queue = [c for c in queue if c["id"] not in done_ids][:max(0, args.limit - len(done_ids))]
        if not queue and not threads:
            print("aucune feuille à traiter", flush=True)
            break
        waiting = [c for c in queue if target_level(c, levels) is None]
        queue = [c for c in queue if target_level(c, levels) is not None]
        if waiting and not getattr(main, "_warned", False):
            print(f"{len(waiting)} feuille(s) escaladée(s) au-dessus des niveaux de la réserve : en attente "
                  f"({' '.join(c['id'] for c in waiting[:20])})", flush=True)
            main._warned = True
        if not queue and not threads:
            print("aucune feuille à traiter pour cette réserve", flush=True)
            break
        launched = False
        for model, slots in pool:
            mine = [c for c in queue if target_level(c, levels) == level_of(model)]
            if not mine:
                continue
            if breakers[family(model)].blocked():
                continue
            busy = max(sum(1 for _, m in threads if m == model), len(running_agents(model)))
            while busy < slots and mine:
                batch, mine = mine[:args.batch], mine[args.batch:]
                queue = [c for c in queue if c not in batch]
                ids, tag, before, prompt = assign(batch, model, n_batch)
                done_ids.update(ids)
                n_batch += 1

                def work(ids=ids, tag=tag, before=before, prompt=prompt, model=model):
                    tg, dt, res, log = run_batch(ids, tag, before, prompt, model, args, breakers[family(model)])
                    print(f"[{tg}] {dt:.0f}s  " + "  ".join(f"{i}:{st}" for i, st in res)
                          + f"  ({os.path.relpath(log, GAMES_DIR)})", flush=True)

                th = threading.Thread(target=work)
                th.start()
                threads.append((th, model))
                busy += 1
                launched = True
                time.sleep(3)  # étale les démarrages
        if launched:
            continue
        all_blocked = all(b.blocked() for b in breakers.values())
        if all_blocked and not threads and queue:
            resumes = [b.until for b in breakers.values() if b.until]
            if not (args.wait_quota and resumes):
                alert("toutes les familles de modèles sont en pause : arrêt (relancer plus tard)")
                sys.exit(2)
            wake = min(resumes)
            alert(f"toutes les familles en pause : reprise automatique vers "
                  f"{time.strftime('%H:%M', time.localtime(wake))}", urgent=False)
            while time.time() < wake and not os.path.exists(STOP):
                time.sleep(30)
            continue
        time.sleep(10)
    for t, _ in threads:
        t.join()


if __name__ == "__main__":
    main()
