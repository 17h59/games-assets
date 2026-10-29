# Test headless : Brendan, dans la démo, ne traverse pas la maison au nord de son point de départ.
#   godot --headless --path rpg --script res://godot/tests/collision_test.gd
extends SceneTree

var player: CharacterBody2D
var frames := 0


func _initialize() -> void:
	var demo: Node = (load("res://godot/demo/demo.tscn") as PackedScene).instantiate()
	root.add_child(demo)
	player = demo.get_node("Joueur")
	player.set_physics_process(false)


func _physics_process(_delta: float) -> bool:
	frames += 1
	if frames < 5:
		return false
	var start := player.position
	var hit := player.move_and_collide(Vector2(0, -200))
	print("départ ", start, " arrivée ", player.position, " collision ", hit != null)
	return true
