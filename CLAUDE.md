# Projet : RPG Godot avec assets GBA ripés

**Si tu es un agent de vérification lancé par `tools/delegate.py`** (ta consigne parle de feuilles
assignées) : ignore tout ce qui suit et ne lis pas docs/ ; suis uniquement `tools/AGENT_GUIDE.md`.

La documentation complète (mémoire de travail) est dans [docs/README.md](docs/README.md) : la lire en
premier, surtout après une remise à zéro du contexte (section « Reprendre le travail en 5 minutes »).

Règles essentielles (détails dans docs/projet.md) :
- Répondre en français. Les nouvelles idées d'amélioration des outils peuvent être implémentées sans demander
  (autorisation donnée le 2026-10-29) ; les noter dans docs/historique.md.
- Ne JAMAIS lancer `tools/spriters_scraper.py` (contourne Cloudflare) : donner la commande à l'utilisateur.
- Travail répétitif / vérification visuelle → agents via `tools/delegate.py` : Haiku 5.5 par Claude Code
  (`cc:`) d'abord, escalade vers Gemini (agy) quand il galère : `--allow-agy --pool escalade` (docs/delegation.md).
- Corriger les OUTILS (`tools/spritekit`), pas les sorties ; tout réglage passe par `tools/sk`.
- Tout nouvel outil ou paramètre : mettre à jour `tools/AGENT_GUIDE.md` ET la page docs concernée,
  et ajouter une ligne dans docs/historique.md ; tenir docs/limites-et-reste-a-faire.md à jour.
