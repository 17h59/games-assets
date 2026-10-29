# Génère les ressources Godot à partir de res://godot/catalog.json (écrit par `tools/sk godot`).
#   godot --headless --path rpg --import            (une fois : importe les PNG)
#   godot --headless --path rpg --script res://godot/tools/build_resources.gd
# Sorties : res://godot/sprite_frames/<jeu>/<feuille>/<entité>.tres (SpriteFrames, animations nommées)
#           res://godot/tilesets/pmd/<donjon>.tres (TileSet 24 px, terrains walls / ground / water)
#           res://godot/demo/demo.tscn (scène de démo, voir build_demo)
extends SceneTree

const CATALOG := "res://godot/catalog.json"
const TERRAIN_COLORS := {"walls": Color(0.45, 0.3, 0.15), "ground": Color(0.9, 0.8, 0.4), "water": Color(0.2, 0.5, 1.0)}
const TERRAIN_INDEX := {"walls": 0, "ground": 1, "water": 2}

var stats := {"sprite_frames": 0, "tilesets": 0, "cartes": 0, "erreurs": 0}


func _init() -> void:
	var cat: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
	for e in cat["entities"]:
		_sprite_frames(e)
	for t in cat["terrains"]:
		_tileset(t)
	var poke := {}
	for t in cat.get("poke_terrains", []):
		poke[t["id"]] = _poke_tileset(t)
	var libs := {}
	for game in cat.get("tile_libraries", {}):
		libs[game] = _library_tileset(game, cat["tile_libraries"][game])
	for m in cat.get("maps", []):
		if libs.has(m["game"]):
			_map_scene(m, libs[m["game"]], cat["tile_libraries"][m["game"]])
	_build_demo(cat)
	_build_town_demo()
	_build_edges_demo(cat, poke)
	_build_galleries(cat)
	print("ressources : ", stats)
	quit()


func _save(res: Resource, path: String) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var err := ResourceSaver.save(res, path)
	if err != OK:
		stats["erreurs"] += 1
		push_error("échec d'écriture %s (%d)" % [path, err])


func _sprite_frames(e: Dictionary) -> void:
	var texs := []
	for p in e["textures"]:
		var tex: Texture2D = load(p)
		if tex == null:
			stats["erreurs"] += 1
			return
		texs.append(tex)
	var frames := SpriteFrames.new()
	frames.remove_animation("default")
	for name in e["animations"]:
		var a: Dictionary = e["animations"][name]
		frames.add_animation(name)
		frames.set_animation_speed(name, a["fps"])
		frames.set_animation_loop(name, a["loop"])
		for fr in a["frames"]:  # [indice de texture, x, y, l, h]
			var at := AtlasTexture.new()
			at.atlas = texs[int(fr[0])]
			at.region = Rect2(fr[1], fr[2], fr[3], fr[4])
			frames.add_frame(name, at)
	_save(frames, "res://godot/sprite_frames/%s.tres" % e["id"])
	stats["sprite_frames"] += 1


func _tileset(t: Dictionary) -> TileSet:
	var ts := TileSet.new()
	var size: int = t["tile"]
	ts.tile_size = Vector2i(size, size)
	ts.add_terrain_set(0)
	ts.set_terrain_set_mode(0, TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES)
	for name in TERRAIN_INDEX:
		ts.add_terrain(0)
		ts.set_terrain_name(0, TERRAIN_INDEX[name], name)
		ts.set_terrain_color(0, TERRAIN_INDEX[name], TERRAIN_COLORS[name])
	for g in t["groups"]:
		var tex: Texture2D = load(g["texture"])
		if tex == null:
			stats["erreurs"] += 1
			continue
		var src := TileSetAtlasSource.new()
		src.texture = tex
		src.texture_region_size = Vector2i(size, size)
		ts.add_source(src)
		var terr: int = TERRAIN_INDEX[g["terrain"]]
		for tl in g["tiles"]:
			var c := Vector2i(int(tl["col"]), int(tl["row"]))
			src.create_tile(c)
			var td := src.get_tile_data(c, 0)
			td.terrain_set = 0
			td.terrain = terr
			td.probability = 0.15 if g["alt"] else 1.0
			for bit in tl["peering"]:
				td.set_terrain_peering_bit(_neighbor(bit), terr)
	_save(ts, "res://godot/tilesets/pmd/%s.tres" % t["id"])
	stats["tilesets"] += 1
	return ts


# Bords de terrains Pokémon : un TileSet par jeu, une source (atlas des terrains), un jeu de terrains
# (coins + côtés) ; tuiles pures = terrain sur les 8 voisins, transitions = voisins mixtes.
func _poke_tileset(t: Dictionary) -> TileSet:
	var ts := TileSet.new()
	var size: int = t["tile"]
	ts.tile_size = Vector2i(size, size)
	ts.add_terrain_set(0)
	ts.set_terrain_set_mode(0, TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES)
	for i in t["terrains"].size():
		var tr: Dictionary = t["terrains"][i]
		ts.add_terrain(0)
		ts.set_terrain_name(0, i, tr["name"])
		ts.set_terrain_color(0, i, Color8(int(tr["color"][0]), int(tr["color"][1]), int(tr["color"][2])))
	var src := TileSetAtlasSource.new()
	src.texture = load(t["texture"])
	if src.texture == null:
		stats["erreurs"] += 1
		return ts
	src.texture_region_size = Vector2i(size, size)
	ts.add_source(src, 0)
	for tl in t["tiles"]:
		var c := Vector2i(int(tl["col"]), int(tl["row"]))
		if src.has_tile(c):
			continue
		src.create_tile(c)
		var td := src.get_tile_data(c, 0)
		td.terrain_set = 0
		td.terrain = int(tl["terrain"])
		td.probability = float(tl.get("probability", 1.0))
		for bit in tl["peering"]:
			td.set_terrain_peering_bit(_neighbor(bit), int(tl["peering"][bit]))
	_save(ts, "res://godot/tilesets/terrains_%s.tres" % t["id"])
	stats["tilesets"] += 1
	return ts


# Démo des bords Pokémon : pour chaque paire de terrains (les 12 premières), un carré du terrain B
# peint par set_cells_terrain_connect au milieu du terrain A : les bords sont choisis par Godot.
func _build_edges_demo(cat: Dictionary, poke: Dictionary) -> void:
	for t in cat.get("poke_terrains", []):
		var root := Node2D.new()
		root.name = "Bords_" + t["id"]
		var layer := TileMapLayer.new()
		layer.name = "Sol"
		layer.tile_set = poke[t["id"]]
		root.add_child(layer)
		layer.owner = root
		var k := 0
		for pr in t["pairs"].slice(0, 12):
			var ox := (k % 4) * 10
			var oy := (k / 4) * 10
			var a: Array[Vector2i] = []
			var b: Array[Vector2i] = []
			for y in 9:
				for x in 9:
					a.append(Vector2i(ox + x, oy + y))
					if x >= 3 and x <= 5 and y >= 2 and y <= 6 or x >= 2 and x <= 6 and y >= 3 and y <= 5:
						b.append(Vector2i(ox + x, oy + y))
			layer.set_cells_terrain_connect(a, 0, int(pr[0]))
			layer.set_cells_terrain_connect(b, 0, int(pr[1]))
			k += 1
		var cam := Camera2D.new()  # toute la grille 40x30 tuiles dans l'écran 240x160
		cam.position = Vector2(320, 240)
		cam.zoom = Vector2(0.33, 0.33)
		root.add_child(cam)
		cam.owner = root
		var scene := PackedScene.new()
		scene.pack(root)
		_save(scene, "res://godot/demo/bords_%s.tscn" % t["id"])


# TileSet d'un jeu : une source par page d'atlas de la bibliothèque (identifiant de source = n° de page).
func _library_tileset(game: String, lib: Dictionary) -> TileSet:
	var ts := TileSet.new()
	var size: int = lib["tile"]
	ts.tile_size = Vector2i(size, size)
	var srcs := []
	for k in lib["pages"].size():
		var src := TileSetAtlasSource.new()
		src.texture = load(lib["pages"][k])
		src.texture_region_size = Vector2i(size, size)
		ts.add_source(src, k)
		srcs.append(src)
	for tl in lib["tiles"]:
		srcs[int(tl[0])].create_tile(Vector2i(int(tl[1]), int(tl[2])))
	# collisions : carré plein sur les tuiles « solides » (pas du sol)
	ts.add_physics_layer()
	var half := size / 2.0
	var square := PackedVector2Array([Vector2(-half, -half), Vector2(half, -half), Vector2(half, half), Vector2(-half, half)])
	for i in lib.get("solid", []):
		var tl: Array = lib["tiles"][int(i)]
		var td := (srcs[int(tl[0])] as TileSetAtlasSource).get_tile_data(Vector2i(int(tl[1]), int(tl[2])), 0)
		td.add_collision_polygon(0)
		td.set_collision_polygon_points(0, 0, square)
	_save(ts, "res://godot/tilesets/%s.tres" % game)
	stats["tilesets"] += 1
	return load("res://godot/tilesets/%s.tres" % game)


# Carte d'origine reconstruite en TileMapLayer (grille de region_N.json : indices de la bibliothèque, -1 = vide).
func _map_scene(m: Dictionary, ts: TileSet, lib: Dictionary) -> void:
	var g: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(m["json"]))
	var layer := TileMapLayer.new()
	layer.name = String(m["id"]).get_file()
	layer.tile_set = ts
	var tiles: Array = lib["tiles"]
	var grid: Array = g["grid"]
	for y in grid.size():
		var row: Array = grid[y]
		for x in row.size():
			var i := int(row[x])
			if i >= 0:
				var tl: Array = tiles[i]
				layer.set_cell(Vector2i(x, y), int(tl[0]), Vector2i(int(tl[1]), int(tl[2])))
	var scene := PackedScene.new()
	scene.pack(layer)
	_save(scene, "res://godot/maps/%s.tscn" % m["id"])
	stats["cartes"] += 1


# Galeries (pour parcourir les assets dans l'éditeur) : res://godot/galeries/<jeu>_<catégorie>.tscn
# Une case par entité animée (première animation jouée en boucle) ou par objet, avec son nom en petit.
func _build_galleries(cat: Dictionary) -> void:
	var groups := {}
	for e in cat["entities"]:
		if e["name"] == "_feuille":
			continue
		var key := "%s_%s" % [e["game"], e["category"]]
		if not groups.has(key):
			groups[key] = []
		groups[key].append(e)
	for o in cat["objects"]:
		var key := "%s_objets" % o["game"]
		if not groups.has(key):
			groups[key] = []
		groups[key].append(o)
	for key in groups:
		var root := Node2D.new()
		root.name = key
		var x := 0
		var y := 0
		var row_h := 0
		for it in groups[key]:
			var node: Node2D
			var w := 32
			var h := 32
			if it.has("animations"):
				var path := "res://godot/sprite_frames/%s.tres" % it["id"]
				if not ResourceLoader.exists(path):
					continue
				var sf: SpriteFrames = load(path)
				if sf == null or sf.get_animation_names().is_empty():
					continue
				var an := AnimatedSprite2D.new()
				an.sprite_frames = sf
				var first: String = an.sprite_frames.get_animation_names()[0]
				an.animation = first
				an.autoplay = first
				an.centered = false
				w = int(it["cell"][0]) if it.has("cell") else 32
				h = int(it["cell"][1]) if it.has("cell") else 32
				node = an
			else:
				var sp := Sprite2D.new()
				sp.texture = load(it["texture"])
				if sp.texture == null:
					continue
				sp.centered = false
				w = sp.texture.get_width()
				h = sp.texture.get_height()
				node = sp
			if x + w > 1200:
				x = 0
				y += row_h + 14
				row_h = 0
			node.position = Vector2(x, y + 10)
			node.name = String(it["id"]).get_file().validate_node_name()
			root.add_child(node)
			node.owner = root
			var lab := Label.new()
			lab.text = String(it["id"]).get_file()
			lab.position = Vector2(x, y)
			lab.add_theme_font_size_override("font_size", 6)
			root.add_child(lab)
			lab.owner = root
			x += max(w, 40) + 8
			row_h = max(row_h, h)
		var scene := PackedScene.new()
		scene.pack(root)
		_save(scene, "res://godot/galeries/%s.tscn" % key)


func _neighbor(name: String) -> int:
	match name:
		"TOP_SIDE": return TileSet.CELL_NEIGHBOR_TOP_SIDE
		"TOP_RIGHT_CORNER": return TileSet.CELL_NEIGHBOR_TOP_RIGHT_CORNER
		"RIGHT_SIDE": return TileSet.CELL_NEIGHBOR_RIGHT_SIDE
		"BOTTOM_RIGHT_CORNER": return TileSet.CELL_NEIGHBOR_BOTTOM_RIGHT_CORNER
		"BOTTOM_SIDE": return TileSet.CELL_NEIGHBOR_BOTTOM_SIDE
		"BOTTOM_LEFT_CORNER": return TileSet.CELL_NEIGHBOR_BOTTOM_LEFT_CORNER
		"LEFT_SIDE": return TileSet.CELL_NEIGHBOR_LEFT_SIDE
		_: return TileSet.CELL_NEIGHBOR_TOP_LEFT_CORNER


# Démo : un donjon Donjon Mystère peint par terrains (murs autour, sol, une mare), le héros d'Émeraude
# qui marche (flèches), et quelques objets de cartes posés dessus.
func _build_demo(cat: Dictionary) -> void:
	var terr: Dictionary = {}
	for t in cat["terrains"]:
		if t["id"] == "tiny_woods":
			terr = t
	if terr.is_empty() and not cat["terrains"].is_empty():
		terr = cat["terrains"][0]
	var root := Node2D.new()
	root.name = "Demo"
	if not terr.is_empty():
		var ts: TileSet = load("res://godot/tilesets/pmd/%s.tres" % terr["id"])
		var layer := TileMapLayer.new()
		layer.name = "Donjon"
		layer.tile_set = ts
		root.add_child(layer)
		layer.owner = root
		var w := 24
		var h := 18
		var walls: Array[Vector2i] = []
		var ground: Array[Vector2i] = []
		var water: Array[Vector2i] = []
		for y in h:
			for x in w:
				var c := Vector2i(x, y)
				var border := x < 2 or y < 2 or x >= w - 2 or y >= h - 2
				var pillar := (x in [7, 8] and y in [6, 7]) or (x in [16, 17] and y in [10, 11])
				var pond := Vector2(x, y).distance_to(Vector2(13, 12)) < 2.6
				if border or pillar:
					walls.append(c)
				elif pond:
					water.append(c)
				else:
					ground.append(c)
		layer.set_cells_terrain_connect(ground, 0, TERRAIN_INDEX["ground"])
		layer.set_cells_terrain_connect(walls, 0, TERRAIN_INDEX["walls"])
		layer.set_cells_terrain_connect(water, 0, TERRAIN_INDEX["water"])
	var props := Node2D.new()
	props.name = "Objets"
	root.add_child(props)
	props.owner = root
	var n := 0
	for o in cat["objects"]:
		if o["game"] == "emerald" and o["validation"] == "verified" and o["size_tiles"][0] <= 2 and o["size_tiles"][1] <= 2 and n < 6:
			var sp := Sprite2D.new()
			sp.texture = load(o["texture"])
			sp.centered = false
			sp.position = Vector2(80 + n * 40, 60 + (n % 2) * 150)
			props.add_child(sp)
			sp.owner = root
			n += 1
	var player := CharacterBody2D.new()
	player.name = "Joueur"
	player.position = Vector2(120, 100)
	player.set_script(load("res://godot/demo/player.gd"))
	root.add_child(player)
	player.owner = root
	var anim := AnimatedSprite2D.new()
	anim.name = "Sprite"
	anim.sprite_frames = load("res://godot/sprite_frames/emerald/brendan/walk.tres")
	anim.animation = "idle_down"
	anim.offset = Vector2(0, -8)
	player.add_child(anim)
	anim.owner = root
	var cam := Camera2D.new()
	cam.name = "Camera"
	player.add_child(cam)
	cam.owner = root
	var scene := PackedScene.new()
	scene.pack(root)
	_save(scene, "res://godot/demo/demo_donjon.tscn")


# Démo principale : Bourg-en-Vol (carte d'Émeraude reconstruite en TileMapLayer) + Brendan.
func _build_town_demo() -> void:
	var root := Node2D.new()
	root.name = "DemoBourg"
	var map_path := "res://godot/maps/emerald/littleroot_town_19776_r0.tscn"
	if ResourceLoader.exists(map_path):
		var map: Node = (load(map_path) as PackedScene).instantiate()
		root.add_child(map)
		map.owner = root
	var player := CharacterBody2D.new()
	player.name = "Joueur"
	player.position = Vector2(14 * 16 + 8, 21 * 16)
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(10, 8)
	shape.shape = rect
	shape.position = Vector2(0, -2)
	player.add_child(shape)
	player.set_script(load("res://godot/demo/player.gd"))
	root.add_child(player)
	player.owner = root
	var anim := AnimatedSprite2D.new()
	anim.name = "Sprite"
	anim.sprite_frames = load("res://godot/sprite_frames/emerald/brendan/walk.tres")
	anim.animation = "idle_down"
	anim.offset = Vector2(0, -8)
	player.add_child(anim)
	anim.owner = root
	shape.owner = root
	var cam := Camera2D.new()
	cam.name = "Camera"
	player.add_child(cam)
	cam.owner = root
	var scene := PackedScene.new()
	scene.pack(root)
	_save(scene, "res://godot/demo/demo.tscn")
