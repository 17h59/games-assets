# Historique des décisions

[← Sommaire](README.md)

## 2026-10-27
- **Téléchargement** : `curl` bloqué par Cloudflare ; le rejeu du cookie `cf_clearance` a été refusé
  (contournement anti-bot). Claude in Chrome : 12 feuilles puis téléchargements multiples bloqués par Chrome.
  L'utilisateur a écrit son propre scraper et le lance lui-même ([Sources](sources.md)).
- **Outils Python plutôt que MCP Aseprite** pour le découpage de masse (rapide, reproductible). Aseprite
  servira à la création / retouche plus tard.
- **Architecture « fiches + outil déterministe + agents vérificateurs »** pour économiser les tokens de
  Claude ([Délégation](delegation.md)). Gemini via `agy` (le CLI était dans `~/.local/bin`, la mémoire ne
  le mentionnait pas encore).
- Premier tri par catégories (`build_assets.py`) abandonné puis supprimé : il ne faisait que nettoyer des
  feuilles entières ; remplacé par `sk`.
- **Fond** : détection mono-couleur → multi-couleurs du bord (damiers) → épluchage de fonds emboîtés.
- **Texte** : critère « ≤ 3 couleurs » remplacé par la part de couleur dominante (texte anti-aliasé).
- **Cartes** : grille par unicité biaisée (perte d'une rangée de bord) → comparaison à nombre de tuiles
  égal ; puis référence par bootstrap ; puis seules les correspondances propres à un décalage comptent.
- **Objets** : soudures statistiques (maisons en lamelles) → composantes non-terrain ; terrain = répété
  dans les 2 directions ; murs = séparateurs ; terrain enfermé inclus ; sol de référence pris à l'extérieur.
- **Pilote Gemini** : 2 feuilles, diagnostics justes ; deux limites d'outil trouvées (plancher d'aire de
  l'épluchage, PNJ 3+3 collés → `_partition`).
- **Grilles** (idée de l'utilisateur sur les répétitions) : grille rigide insuffisante (feuilles assemblées
  à la main) → gouttières (mélangeait les sous-grilles) → **xycut récursif**. Mode `auto` activé par défaut
  seulement pour les feuilles non encore traitées ; les feuilles déjà traitées sont figées `layout=blobs`.
- Idées validées par l'utilisateur puis implémentées : **zones** (son idée), déchets auto, doublons globaux,
  validation auto **marquée non vérifiée**, contrôle de palette, groupe par palette, réglages hérités, miroirs.
- **Quota agy** épuisé après ~90 feuilles : disjoncteur ajouté, puis reprise automatique (`--wait-quota`).
- **Journal + reprise** (exigence de l'utilisateur) : journal append-only, reprise des feuilles interrompues
  avec consigne de reprise, 3 tentatives max ([Journal](journal.md)).
- **13 needs_fix** analysés → `group=columns/blocks`, `carve`, fond par zone, correctif du pas (k ≥ 2),
  grille imposée appliquée même à un bloc soudé ; feuilles relancées avec pistes.
- Documentation `docs/` créée (cette documentation) à la demande de l'utilisateur, comme mémoire de Claude.
- **Réserve multi-modèles** (demande de l'utilisateur) : chaque famille de modèles agy a son propre quota ;
  `--pool`, un disjoncteur par famille, l'arrêt n'a lieu que si toutes sont épuisées. L'ancien répartiteur
  (un seul modèle, en attente jusqu'à 23 h 09) a été arrêté : l'utilisateur ne voulait pas de relance immédiate.
- **Pilotes Haiku 5.5** : 6 feuilles ; suit le guide, lit les planches (14 PNG sur 3 feuilles), trouve un bug (planche results
  qui plantait sur un élément > 1400 px, corrigé) ; moins précis que Gemini (2 éléments doubles laissés, animation
  d'effet non regroupée → consignes ajoutées au guide).
- **agy désactivé** (plus de quota) ; ajout du moteur **Claude Code** (`cc:`) avec **Haiku 5.5** par défaut
  (4 agents), outils limités à `tools/sk` + Read. Même journal, reprise et disjoncteurs.
- **Effets / monstres / persos Zelda validés mais rangés en vrac** (signalé par l'utilisateur) : le
  regroupement en animations n'existait que pour les persos Pokémon et n'était pas exigé des agents. →
  **étapes obligatoires** confirmées (`sk check`, `ok` bloqué, caducité, `sk coverage`, marqueurs
  A_VERIFIER), **ensembles par légende** (`sets=captions`, `sk captions`, `sk setname`), `group=anim`,
  aperçus PNG des cartes + confirmations automatiques ; migration (92 feuilles en relecture).
- `maps/` ne contenait que du JSON sans explication → aperçus PNG + doc.
- **1er lot Haiku (étapes)** : 120 feuilles en 40 min, 67 ok / 53 needs_fix. Causes : bug (setnames + zones
  → KeyError, trouvé par 4 agents), légendes à droite / centrées / même ligne mal rattachées, pas d'outil
  pour regrouper à la main, découpe de sprites collés trop technique, légendes illisibles, hésitations.
  → `sk entity`, `sk slice`, `sk setbox`, rattachement par segment, planche lisible, règles « Décider sans
  bloquer » ; 53 feuilles relancées. Contrôle d'échantillon : erreurs de lecture des légendes (Blast Burn
  nommé blaze_burn).
- Fichiers nommés d'après leur ensemble (`blast_burn_000.png`). `sk recon` (reconstruction par feuille) et
  section « cartes » du guide + `--type map` dans le répartiteur, pour faire confirmer l'étape `grille`.
- **Bug de concurrence** : les fiches étaient écrites en place (fichier vidé puis réécrit) ; le répartiteur a lu
  une fiche vide pendant qu'un agent l'écrivait → JSONDecodeError, fil principal mort (agents en cours finis,
  plus aucun lot lancé). → `config.write_json_atomic` (temporaire + os.replace) pour fiches et manifests,
  lecture tolérante `_read_json` ; répartiteur relancé.
- Haiku cale sur les feuilles les plus complexes (Link sans capuchon, Ezlo, PNJ d'Hyrule : conclut sans
  corriger) : envisager Sonnet pour les needs_fix restants (à valider par l'utilisateur, coût).
- **2e lot Haiku** : 101 ok, 19 needs_fix (feuilles très complexes). Deux bugs signalés : merge entre zones et
  drop d'un élément chevauchant une zone → corrections appliquées sur la feuille entière (sauf carve/split),
  fusion avec pixels conservés. **`sk regress`** créé : un changement d'outil a modifié la sortie de 2 feuilles
  validées sans toucher leur fiche → relecture ; régénération des 100 autres (noms de fichiers par ensemble).

## 2026-10-28
- Nouveau quota Gemini (compte Google changé), mais agy demande une reconnexion (« Waiting for authentication ») :
  à faire par l'utilisateur (`! agy`), jamais par Claude.
- **Outils pour les 6 feuilles bloquées par l'outil** (validés par l'utilisateur) : `sk pixel` (lire une couleur),
  `sk erase` (gomme par couleur dans un rectangle, avec remplissage `near` / motif `LxH`), `sk flood` (région
  d'une couleur → transparente). Retouches calculées sur l'image source, avant détection. `sk regress` : 105
  feuilles identiques.
- **Escalade Haiku → Gemini Flash → Gemini Argon** dans `delegate.py` (demande de l'utilisateur : Haiku d'abord,
  Gemini dès que Haiku galère, quota agy limité) : niveaux par fiche, `--pool escalade`, contrôle « ok sans
  planche lue ».
- **`sk report`** : récapitulatif chiffré (avancement, auteurs, temps, coût, estimations).
- Les 17 `needs_fix` repassés en `needs_review` au niveau 1 (Gemini), avec les nouveaux outils dans leur note.
- **18 h 36, 1er contrôle autonome.** Les 17 sprites difficiles : tous `ok` par Gemini Flash (8 lots, 12-35 min
  chacun ; gommes / remplissages très utilisés ; contrôle visuel de 8142 : propre). Sprites : 100 %.
- Bug `--limit` : appliqué à chaque tour de la boucle → le « pilote » de 10 cartes a tout pris (62 cartes ok
  en 2 h). Corrigé : limite TOTALE par lancement.
- Cartes escaladées en série vers Gemini sans raison de vision : (1) `sk erase` sans effet sur les cartes
  (`tiles.load` ignorait les retouches) → corrigé ; (2) reconstruction < 97 % due au décor hors grille /
  crédits → guide : confirmer `reconstruction ok` avec note dans ce cas, `needs_fix` seulement si les tuiles
  sont fausses ; (3) cartes PMD (tuile 24, pas de bibliothèque) : limite connue → **PMD exclu** de la
  délégation (`--game` accepte une liste) jusqu'au support PMD. Répartiteur cartes arrêté (STOP) puis relancé
  (`batch11_cartes.out`, emerald,ruby_sapphire,minish_cap).
- **20 h 06, 2e contrôle** : 1 h 15 perdue. Le script d'attente (`while pgrep -f "tools/delegate.py"`) se
  trouvait LUI-MÊME (la chaîne est dans sa propre ligne de commande) → attente infinie, STOP jamais retiré.
  Leçon : attendre un processus par PID (`wait`/`kill -0 PID`) ou `pgrep -f "^.venv/bin/python tools/delegate"`.
  Répartiteur cartes relancé à la main (`batch11_cartes.out`, sans PMD).
- **22 h 36, 3e contrôle** : répartiteur cartes fini à 21 h 08 (« aucune feuille à traiter »). **Cartes
  Émeraude, Rubis/Saphir, Minish Cap : 100 % vérifiées** (147 ok + 1 skip ; 53 reconstructions confirmées à la
  main par les agents avec raison — contrôle visuel de 142450 : justifié). Restent les 157 cartes PMD (exclues).
- Bibliothèques de tuiles construites : `sk tiles ruby_sapphire` (16 225 tuiles, 78 feuilles, 3 min) et
  `sk tiles minish_cap` (14 422 tuiles, 32 feuilles, 30 s). Confirmations des cartes intactes.

## 2026-10-29 (nuit, utilisateur absent, autorisation générale : « fais tout, nouvelles idées sans demander »)
- **Autorisation** : les nouvelles idées d'amélioration des outils s'implémentent sans demander (CLAUDE.md,
  projet.md, mémoire mis à jour).
- **8303** vérifiée par Haiku : sprites 122/122 ok.
- **Revue hostile** (sous-agent Opus, lecture seule) : 8 critiques, 12 importantes. Appliqué :
  C1 `sk set status=` refusé ; C2 `regress` vide les confirmations des sorties changées, détecte les cases
  d'animation recalculées ; C3 `extract.run` remet les marqueurs (`refresh_marker`) — 122 manifests corrigés ;
  **C4 frames en escalier** (ligne de base par rangée, `_row_lift`) : 26 feuilles, dont la marche de Brendan
  (case 14x65 → 14x21) ; C7 un `skip` d'agent est escaladé ; C8 sauvegarde git de `rpg/pipeline` (fiches,
  journal) + commit par lot, garde-fou agents (`_guard` : pas de commande globale, seulement les fiches de son
  lot, pas de `clear all`) ; I1 escalade seulement si un niveau existe ; I2 escalade = confirmations vidées ;
  I3 quota cherché dans les messages du moteur seulement, pause 30 min par défaut ; I4 `release_stale` ignore
  les lots vivants ; I6 `check` refusé si la fiche a changé depuis le dernier `run` (`run_state`) ;
  I7 `run` ne rétrograde plus needs_fix / skip / ok valide ; I9 signature d'objet = contenu ; I11 répartiteur
  signé ; I12 `--ids` respecte `assigned`. Pas encore fait : C5 (grilles), C6 (effets plein écran), I5
  (verrou global des fiches), I8 (gabarits directionnels), I10.
- **Objets v2/v3** : pages de vérification `obj_<jeu>_NN`, murs par le vide, sol par tuile, ombres
  semi-transparentes, découpage auto par connexité de pixels. Pilote Haiku : planches 40 objets illisibles →
  10 par image ; Haiku ne découpait jamais → découpage auto. Pages refaites de zéro (anciennes dans git).
- **PMD** : 60 tilesets = tables d'autotiles → type `terrainset`, `pmd.py` (atlas + motifs de voisins),
  magenta = transparence ; 105 « maps » = décors peints → `sprites`/`scenes`, `peel=0`.
- **Godot** : projet créé, `sk godot` + `build_resources.gd`, 1 884 SpriteFrames, TileSet PMD à terrains, démo
  (capture : donjon peint par terrains + Brendan).
- **Objets v4** (01 h 55) : contrôle visuel → Centre Pokémon troué (ses tuiles, présentes dans toutes les villes,
  passaient pour du sol). Sol = plus de tuile « rigide » (voisin le plus fréquent ≥ 60 % dans ≥ 3 directions
  = morceau de bâtiment). Sols candidats élargis aux tuiles de terrain de couleur proche (eau à vagues
  décalées). Pages refaites de zéro (3e fois ; anciennes décisions dans git). Rubis/Saphir 66 pages,
  Émeraude 30, Minish Cap 14.
- **Audit Haiku** : `sk audit --n 8` → 8 feuilles ok de Haiku renvoyées à Gemini (rapport : `sk audit --report`).
- **Effets plein écran** : `panel_frames` (un encadré = une frame, fond transparent) ; anomalies `pulverise` et
  `no_entity` (effets) ; Rain et Weather Effects renvoyés à Gemini.
- **`sk anims ID eN walk_down=…`** : animations nommées d'une entité ; export Godot : une SpriteFrames par
  entité + une par feuille de persos/monstres (toutes ses entités comme animations : Zelda).
- **Godot** : TileSet par jeu (bibliothèque) + 723 cartes reconstruites en TileMapLayer ; démo = Bourg-en-Vol.
- **Bords de terrains Pokémon** (`terrains.py`, expérimental) : transitions « mélange exact de deux sols » trop
  rares (liserés) → autotile Pokémon/Minish non fait ; PMD a de vrais autotiles (fait).
- **Grilles (revue C5)** : mesure « tuiles uniques dans la bibliothèque » → Pokémon sain ; Minish : décors peints.
- **02 h 47, contrôle** : terrains PMD 59/60 ok, décors PMD en cours (~70 ok), objets 52/110 ok.
  **Audit Haiku : 5 désaccords sur 8** (Gemini corrige : regroupement de « Sword » en 4 directions x 9 frames,
  11 animations nommées d'Acrobandits, points des i/j perdus dans « Font », noms d'entités). Conclusion :
  la validation Haiku seule n'est pas fiable sur les feuilles complexes → **audit élargi** : les 70 feuilles
  personnages / monstres / effets validées uniquement par Haiku renvoyées à Gemini (`batch21_audit2.out`,
  `batch22_audit_persos.out`) ; `sk audit --report` mesure l'accord. 85133 : pmd.py applique désormais
  `sk erase` (bug signalé par 3 agents ; corrigé à 01 h 58, vérifié), renvoyée à Gemini.
- **Bords de terrains Pokémon vérifiables** (03 h) : pages `tp_<jeu>_NN` (type `terrainpairs`, étape `bords`,
  6 paires par page, décisions rangées par hash de tuile) ; `sk tdrop ID n…`, `sk tname ID id nom` ; planche
  `qa/ID/bords_0.png` (rouge = partie A, bleu = partie B). 29 pages (Émeraude 15, Rubis/Saphir 14) déléguées
  (`batch24_bords.out`). Export Godot seulement après vérification (à faire). `sk report` compte objets et
  terrains PMD.
- 2026-10-29 05 h 10 : pages d'objets (110) et de bords (29) toutes vérifiées. Export Godot des bords Pokémon :
  `godot._poke_terrains` → `tilesets/terrains_<jeu>.tres` + démos `demo/bords_<jeu>.tscn` (probabilité des
  tuiles pures ∝ fréquence, paires classées par complétude). Résultat honnête : raccords partiels.
  Audit Haiku : 6 accords / 21 (57 en cours chez Gemini).
- 2026-10-29 06 h 50 : bug `delegate.finish_unconcluded` : une feuille interrompue (quota, timeout) repartait
  en `todo` même si elle était `needs_review` → un répartiteur `--status needs_review` la perdait (4 feuilles
  d'audit bloquées). Corrigé (statut d'avant le lot restauré), feuilles remises, répartiteurs relancés
  (`batch25_audit3.out`, `batch26_audit_persos2.out`). Godot : 160 imports `valid=false` (PNG importés pendant
  leur réécriture) → supprimer les `.import` invalides puis `--import` (noté dans docs/godot.md).
- 2026-10-29 08 h 55 : `sk audit --report` donne la nature de chaque désaccord (compare la fiche à sa version
  git au moment de l'audit ; clé absente = vide) : découpage / regroupement / noms. Mesure à 49 feuilles :
  7 accords, découpage 24, regroupement 12, noms 5 → la validation Haiku seule des sprites n'est pas fiable.
  Audit étendu aux pages : 4 `obj_`, 3 `tp_`, 3 tables PMD (lots `batch27_audit_*.out`, Gemini à partir de 13 h 09).

- 2026-10-29 ~10 h : arrêt de tout à la demande de l'utilisateur (PC éteint) : fichier `rpg/pipeline/STOP`
  posé, répartiteurs et agents tués, cron de contrôle supprimé. Pour reprendre : `rm rpg/pipeline/STOP` puis
  relancer les répartiteurs d'audit (`--status needs_review --allow-agy --pool escalade --wait-quota`, types
  sprites, characters, objects, terrainpairs, terrainset).
- 2026-10-29 reprise : quota Gemini Flash épuisé → préréglage `--pool argon` (`cc:claude-haiku-5-5:4@0,
  agy:gemini-4-argon-medium:1@1` : Argon en effort **medium**, pas high, consigne de l'utilisateur). Bug :
  5 répartiteurs lancés ensemble comptaient chacun 0 agent → 3 Argon au lieu d'1. Corrigé : verrou
  `locks/slots_<famille>.lock` autour du comptage + lancement, relâché quand le processus est visible.
- 2026-10-30 revue des 4 `needs_fix` d'Argon (6498, 8183, obj_minish_cap_11, obj_ruby_sapphire_07) : cause
  commune = `delegate.release_stale` d'un répartiteur libérait (« agent disparu ») les feuilles qu'un AUTRE
  répartiteur parallèle venait d'attribuer → l'agent était refusé (« ne fait pas partie de ton lot ») et 2
  tentatives brûlées par lot. Corrigé : `assigned_by` (pid) + `assigned_t` (grâce 180 s) dans la fiche.
- 2026-10-30 `extract` : les points `split` n'étaient pas filtrés par zone ; un point d'une zone re-découpait aussi
  le grand cadre de la partie principale qui l'englobe → chaque sprite entouré recréé en double (8183 : 208 items
  au lieu de 118). Filtrage par zone (comme le documentait corrections.md). Seule 8183 change (30 fiches à split testées).
- 2026-10-30 nouveau param `split_own` (opt-in) : `sk split` ne recrée que les morceaux faits des pixels de l'item
  (l'historique reprend tout ce qui est dans sa boîte : doublons, mais aussi « sauvetages » involontaires sur
  5343/6407/6546 → laissé par défaut). Doublons historiques encore présents sur des fiches ok : 28882, 5342, 31116.
- 2026-10-30 `objects` : un `objsplit` sur un objet issu de la découpe automatique était ignoré et l'objet
  disparaissait de sa page sans morceaux (renumérotation). Nouveau param de page `split_pieces` (opt-in,
  `_late_splits`) ; 13 objets découpés concernés sur des pages ruby_sapphire déjà ok (19, 44, 46, 48, 60, 61, 65).
- 2026-10-30 6498 : Link de référence effacé par ses couleurs (`erase` limité au rectangle) au lieu d'un `carve`
  rectangulaire qui entaillait le ver assemblé.
