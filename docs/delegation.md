# Délégation aux agents agy

[← Sommaire](README.md) · code : `tools/delegate.py` · voir aussi [Journal](journal.md), [Guide des agents](guide-agents.md)

## Pourquoi
Les tokens de Claude coûtent cher : la vérification visuelle répétitive est confiée à des agents **agy**
(CLI Antigravity, `~/.local/bin/agy`). Les agents n'utilisent que `tools/sk` (pas de code, pas de retouche).

## Moteurs, réserve de modèles et quotas
Deux moteurs, choisis par préfixe dans la réserve `--pool "moteur:modèle:places,..."` :
- **`cc:`** = Claude Code non interactif (`claude -p --model X --allowedTools "Bash(tools/sk:*)" Read`) :
  outils limités à `tools/sk` et à la lecture des planches. **Défaut : `cc:claude-haiku-5-5:4`.**
  Testé le 2026-10-27 (Haiku exécute `sk` et répond correctement). `CLAUDE.md` dit aux agents d'ignorer
  la doc et de suivre seulement `tools/AGENT_GUIDE.md`.
- **`agy:`** = Antigravity. **Désactivé** depuis le 2026-10-27 (plus de quota) : refusé sans `--allow-agy`.
  Dans agy chaque famille a son propre quota (Gemini 3.8 Flash, Gemini 4 Argon, Claude Sonnet 5.5,
  Claude Opus 5.5, GPT-OSS 120B), lié au compte Google connecté dans agy.

Famille de quota = moteur + modèle sans niveau d'effort (`family()`), un disjoncteur par famille.
Messages de limite reconnus : agy « Individual quota reached... Resets in 3h15m54s » ; Claude Code
« usage limit reached ... reset at 5pm » (`reset_seconds`).

## Lancer
```
.venv/bin/python tools/delegate.py --status todo,needs_review --batch 3 --timeout 2700 --wait-quota \
  > rpg/pipeline/logs/batchN.out 2>&1          # en arrière-plan
```
`--limit N` = N feuilles AU TOTAL pour ce lancement (corrigé le 2026-10-28) ; `--game a,b` = liste de jeux.
Options : `--pool`, ou `--model X --parallel N` (un seul modèle), `--ids`, `--type`, `--game`,
`--category`, `--limit`, `--max-attempts 3`, `--min-seconds 90`, `--max-suspect 2`, `--reassign`.

## Escalade Haiku → Gemini (2026-10-28)
Demande de l'utilisateur : Haiku fait tout d'abord (pas cher) ; dès qu'il galère, la feuille passe à Gemini
(meilleure vision, quota agy limité). Préréglage `--pool escalade` =
`cc:claude-haiku-5-5:4@0,agy:gemini-3.8-flash-high:2@1,agy:gemini-4-argon-high:1@2` (`@N` = niveau ; défauts
dans `LEVELS`, `MAX_LEVEL = 2`).
- Chaque fiche a un `level` (0 par défaut). Un modèle prend les feuilles dont le niveau cible
  (`target_level` : le plus bas niveau de la réserve ≥ `level`) est le sien. Feuille d'un niveau absent de la
  réserve (ex. niveau 1 sans agy) : en attente, signalée au lancement.
- **Escalade** (`escalate`) au niveau suivant quand un agent d'un niveau < 2 : conclut `needs_fix` ; conclut
  `ok` sans avoir lu une seule planche PNG (contrôlé pour `cc:` par `tool_usage`) ; ou atteint
  `--escalate-after` (2) tentatives sans conclusion. La feuille reprend son statut de travail, `attempts=0`,
  `resume`, `escalations[]` dans la fiche, événement `escalade` au journal ; la consigne de reprise dit au
  modèle suivant pourquoi le précédent a échoué.
- Au niveau 2, `needs_fix` reste `needs_fix` : pour le développeur.
- Le guide des agents dit à Haiku d'utiliser `needs_fix` (avec ce qu'il a essayé) dès qu'il ne voit pas assez bien.
- Chaque lot écrit un événement `lot` (modèle, durée, coût et tokens pour `cc:`) — base du [Récapitulatif](recap.md).

```
.venv/bin/python tools/delegate.py --allow-agy --pool escalade --status todo,needs_review --wait-quota \
  > rpg/pipeline/logs/batchN.out 2>&1
```

## Cartes
`--type map` (ou `tileset`) : lots de cartes seulement, consigne `PROMPT_MAP` (section « Feuilles de CARTES »
du guide : `run`, `gridcheck`, `region`, `recon`, `check grille`). Jamais de lot mélangé cartes / sprites.

## Fonctionnement
- Ordonnanceur en boucle : tant qu'il reste des feuilles au statut demandé, il remplit les places libres de
  chaque modèle de la réserve (places = agents de ce lancement ou d'un précédent, **par modèle**).
- Lots de `--batch` feuilles, marqués `assigned` **avant** le lancement (pas de double attribution) ; nom de
  lot `<date>_b<N>_<famille>`.
- Chaque agent : `claude -p` ou `agy -p` (`agent_cmd`), variable
  `SK_AGENT=agy:<lot>` (signée dans le journal), sortie dans `rpg/pipeline/logs/<lot>.log`.
- Feuilles d'un agent disparu libérées (`release_stale`).

## Ne rien perdre, ne rien laisser inachevé
- Le travail d'un agent est enregistré **commande par commande** dans la fiche : une interruption ne perd
  rien (au pire la dernière commande).
- Feuille non conclue (timeout, fin sans statut, agent disparu) → `todo` + `resume: true` + `attempts+1`,
  événement `interrompu` au journal. Au prochain tour, l'agent reçoit une **consigne de reprise** (réglages,
  corrections, zones, dernière note) : continuer, pas recommencer.
- Après `--max-attempts` (3) tentatives réelles → `needs_fix` (événement `abandon`) pour le développeur.
- Interruption par **quota** : la feuille retrouve son statut, sans compter de tentative.

## Sécurités
- **Quota** (message agy « Individual quota reached... Resets in 3h15m54s », `RESOURCE_EXHAUSTED`, 429) :
  **seule la famille concernée** est mise en pause jusqu'à la remise à zéro annoncée + 5 min ; les autres
  continuent. Alerte dans `rpg/pipeline/ALERT.txt` + notification bureau (`notify-send`).
- **Échecs silencieux** : 2 lots d'affilée d'une famille finis en < 90 s sans conclusion → pause 30 min de
  cette famille.
- **Toutes les familles en pause** : `--wait-quota` attend la première reprise ; sinon sortie code 2.
- `touch rpg/pipeline/STOP` : arrêt propre (les agents en cours finissent).
- Testé avec un faux `agy` (quota simulé) : 3 lots sur 3 familles, pauses séparées, feuilles remises en file.

## Coût / rythme observés
~7 min par feuille ; ~90 feuilles avant épuisement du quota Gemini Flash d'un compte (avant la réserve multi-modèles).
Qualité Gemini : bonne ; diagnostics précis des limites d'outil (voir [Historique](historique.md)).


## Changements du 2026-10-29
- Types délégables : `--type sprites|characters|map|tileset|objects|terrainset` (+ `--category`, `--game`).
- Escalade seulement si la réserve a un niveau au-dessus ; confirmations vidées à l'escalade (le modèle
  suivant refait tout) ; un `skip` posé par un agent est escaladé pour confirmation.
- Quota : recherché seulement dans les événements du moteur (pas dans les sorties de `sk`) ; sans heure de
  remise à zéro, pause de 30 min.
- **Sauvegarde git** de `rpg/pipeline` (sheets/, objects/, journal) : commit automatique après chaque lot
  (`git -C rpg/pipeline log`) ; restaurer une fiche : `git -C rpg/pipeline checkout <commit> -- sheets/...`.
- Plusieurs répartiteurs peuvent tourner ensemble (un par type) : les places par modèle sont comptées sur les
  processus vivants, donc partagées.
