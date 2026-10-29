# Le projet

[← Sommaire](README.md)

## But
L'utilisateur apprend **Godot 4.7** (4.7.2 stable, Arch Linux) en faisant un **RPG au style GBA**. Projet
d'apprentissage, **non diffusé**. Les graphismes viennent de 4 jeux GBA ripés sur The Spriters Resource :
Pokémon Émeraude, Pokémon Rubis/Saphir, Zelda Minish Cap, Pokémon Donjon Mystère Équipe de Secours Rouge.
L'utilisateur **mélange** les assets Zelda et Pokémon dans son jeu.

## Ce que « utilisable » veut dire
Chaque élément **isolé** et réutilisable séparément : chaque PNJ avec ses frames de marche par direction,
chaque objet, chaque effet (y compris de gros rayons), chaque tuile de terrain et ses bords (herbe à côté
de l'eau), chaque maison, et dans les maisons chaque meuble, mur, sol... Puis des ressources Godot
(`SpriteFrames`, `TileSet`, scènes) : voir [Godot](godot.md).

Hors périmètre : les Pokémon eux-mêmes (sections exclues), écrans titres, crédits, mini-jeux.

## Préférences et règles de l'utilisateur
- Parle **français** ; tutoiement ; ton détendu.
- **Coût en tokens** : Claude est réservé au travail minutieux (outils précis et robustes). Le travail
  répétitif / la vérification visuelle va aux agents `agy` (Gemini 3.8 Flash high) : voir [Délégation](delegation.md).
- **Nouvelles idées d'amélioration des outils : autorisées sans demander** depuis le 2026-10-29 (avant : confirmation
  requise). Les tracer dans [historique](historique.md).
- Les validations automatiques doivent être **marquées non vérifiées** : voir [Validation automatique](validation-auto.md).
- Le travail des agents ne doit pas rester inachevé ; il faut un **journal** de ce qui est fini ou pas :
  voir [Journal](journal.md).
- Le **scraper** de l'utilisateur contourne Cloudflare : Claude ne le lance pas, il donne la commande.
  Voir [Sources](sources.md).

## Principe directeur
Améliorer **les outils** plutôt que corriger à la main : toute correction passe par la fiche de la feuille
([Fiches](fiches.md)) et une ré-extraction déterministe. Rien n'est retouché pixel par pixel. Quand un agent
classe une feuille `needs_fix`, c'est presque toujours une limite d'outil à corriger (voir [Historique](historique.md)).
