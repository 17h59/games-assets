# Déplacement 4 directions (flèches) ; animations walk_* / idle_* du SpriteFrames généré.
# La droite n'existe pas dans les feuilles GBA : c'est la gauche retournée (flip_h).
extends CharacterBody2D

const SPEED := 60.0

var facing := "down"


func _physics_process(_delta: float) -> void:
	var dir := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	if absf(dir.x) > absf(dir.y):
		dir.y = 0
	else:
		dir.x = 0
	velocity = dir.normalized() * SPEED
	move_and_slide()
	var sprite: AnimatedSprite2D = $Sprite
	if dir != Vector2.ZERO:
		if dir.x != 0:
			facing = "right" if dir.x > 0 else "left"
		else:
			facing = "down" if dir.y > 0 else "up"
	var side := "left" if facing == "right" else facing
	sprite.flip_h = facing == "right"
	var anim := ("walk_" if dir != Vector2.ZERO else "idle_") + side
	if sprite.animation != anim:
		sprite.play(anim)
