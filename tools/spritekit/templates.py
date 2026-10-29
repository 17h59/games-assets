"""Noms des frames selon la mise en page connue d'un jeu.

Chaque gabarit = liste ordonnée des rôles des frames d'une entité, de gauche à droite.
La direction droite n'est pas stockée quand elle se déduit de la gauche (flip_h dans Godot).
"""

TEMPLATES = {
    "none": [],
    # Pokémon Rubis/Saphir/Émeraude, PNJ en vue de dessus : 3 poses fixes puis 2 pas par direction
    "pokemon_ow9": ["idle_down", "idle_up", "idle_left",
                    "walk_down_1", "walk_down_2", "walk_up_1", "walk_up_2", "walk_left_1", "walk_left_2"],
    # même chose rangée en bloc 3x3 lu ligne par ligne : rangée 1 = poses fixes, 2 = 1er pas, 3 = 2e pas
    "pokemon_ow9_grid": ["idle_down", "idle_up", "idle_left",
                         "walk_down_1", "walk_up_1", "walk_left_1", "walk_down_2", "walk_up_2", "walk_left_2"],
    # variante 3 frames (PNJ immobiles qui tournent seulement la tête)
    "pokemon_ow3": ["idle_down", "idle_up", "idle_left"],
}

# Comment assembler les animations Godot à partir des rôles (rôle de repos réutilisé entre les pas).
ANIMATIONS = {
    "pokemon_ow9": {
        "idle_down": ["idle_down"], "idle_up": ["idle_up"], "idle_left": ["idle_left"],
        "walk_down": ["walk_down_1", "idle_down", "walk_down_2", "idle_down"],
        "walk_up": ["walk_up_1", "idle_up", "walk_up_2", "idle_up"],
        "walk_left": ["walk_left_1", "idle_left", "walk_left_2", "idle_left"],
    },
    "pokemon_ow3": {"idle_down": ["idle_down"], "idle_up": ["idle_up"], "idle_left": ["idle_left"]},
}
ANIMATIONS["pokemon_ow9_grid"] = ANIMATIONS["pokemon_ow9"]


def roles(template: str, n: int):
    names = TEMPLATES.get(template, [])
    return [names[i] if i < len(names) else f"frame_{i}" for i in range(n)]
