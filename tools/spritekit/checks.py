"""Étapes obligatoires et confirmations : chaque feuille doit être traitée AU MOINS UNE FOIS à chaque étape.

Une confirmation = {"result": "ok"|"na", "by": qui, "t": quand, "note": ..., "state": empreinte}.
`state` est l'empreinte des réglages de la fiche (params, overrides, zones, regions) au moment de la
confirmation : si la fiche change ensuite, la confirmation est CADUQUE et l'étape est à refaire.
Le statut `ok` est refusé tant qu'une étape requise n'est pas confirmée sur l'état actuel.
"""
import hashlib
import json
import os
import time

# Étapes requises par type de fiche, avec ce qu'il faut vérifier.
STAGES = {
    "sprites": {
        "decoupage": "chaque élément est entier, seul, sur fond transparent ; légendes / crédits / déchets jetés",
        "regroupement": "les frames d'une même animation / d'un même perso sont regroupées en entités "
                        "(ou « na » si la feuille ne contient que des objets indépendants)",
        "nommage": "animations / persos nommés d'après les légendes de la feuille quand il y en a "
                   "(ou « na » s'il n'y a aucune légende exploitable)",
    },
    "map": {
        "grille": "chaque zone de carte a la bonne grille (ou est ignorée si ce n'est pas une carte)",
        "reconstruction": "la carte reconstruite à partir des tuiles est identique à l'originale (vérifié par l'outil)",
    },
}
STAGES["objects"] = {
    "objets": "chaque objet de la page est entier et seul (pas collé à un mur ou à un autre objet : sinon "
              "objsplit), sol retiré (ombre en noir semi-transparent gardée), textes / étiquettes / bouts de "
              "pièce inutilisables jetés (objdrop)",
}
STAGES["terrainset"] = {
    "terrains": "chaque groupe de colonnes du tableau (Walls, Ground, Water…) est extrait avec le BON nom (lu dans "
                "l'en-tête) et ses tuiles sont entières ; le motif de voisins décodé à gauche correspond à la légende",
}
STAGES["terrainpairs"] = {
    "bords": "chaque tuile numérotée est un vrai bord entre les deux terrains A et B montrés (pas un meuble, une flèche, "
             "un objet posé sur le sol) ; les fausses jetées (tdrop) ; les terrains nommés (tname)",
}
STAGES["characters"] = STAGES["sprites"]
STAGES["tileset"] = STAGES["map"]

STATE_KEYS = ("params", "overrides", "zones", "regions")


def state(cfg):
    blob = json.dumps({k: cfg.get(k) for k in STATE_KEYS}, sort_keys=True, ensure_ascii=False)
    return hashlib.blake2b(blob.encode(), digest_size=8).hexdigest()


def required(cfg):
    return list(STAGES.get(cfg["type"], {}))


def confirm(cfg, stage, result="ok", note="", by=None):
    # revue I6 : on confirme ce qu'on a VU ; si la fiche a changé depuis le dernier `sk run`, la sortie et
    # les planches ne correspondent plus à l'état confirmé
    if by is None and cfg.get("run_state") and cfg["run_state"] != state(cfg):  # l'outil calcule sur l'état actuel
        raise SystemExit(f"la fiche {cfg['id']} a changé depuis le dernier `sk run` (corrections non revues) : "
                         f"relance `tools/sk run {cfg['id']}`, regarde le résultat, puis confirme.")
    if stage not in STAGES.get(cfg["type"], {}):
        raise SystemExit(f"étape inconnue pour le type {cfg['type']} : {stage}. Étapes : {required(cfg)}")
    if result not in ("ok", "na"):
        raise SystemExit("résultat : ok | na")
    cfg.setdefault("checks", {})[stage] = {
        "result": result, "by": by or os.environ.get("SK_AGENT", "manuel"),
        "t": time.strftime("%Y-%m-%d %H:%M:%S"), "note": note, "state": state(cfg)}


def missing(cfg):
    """Étapes non confirmées OU confirmées sur un état antérieur de la fiche."""
    cur = state(cfg)
    out = []
    for st in required(cfg):
        c = cfg.get("checks", {}).get(st)
        if not c:
            out.append((st, "jamais confirmée"))
        elif c.get("state") != cur:
            out.append((st, f"caduque (fiche modifiée depuis le {c['t']})"))
    return out
