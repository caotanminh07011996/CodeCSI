# graphics/scene_manager.py
from PyQt5.QtWidgets import QGraphicsScene
from PyQt5.QtCore import Qt
from .field_drawer import FieldDrawer
from .team_graphic import TeamGraphic
from .ball_item import BallItem
from models.world import World

class SceneManager:
    def __init__(self, world: World):
        self.world = world
        self.scene = QGraphicsScene()
        FieldDrawer().draw(self.scene)

        self.gfx_left  = TeamGraphic(world.team_left,  self.scene, Qt.blue)
        self.gfx_right = TeamGraphic(world.team_right, self.scene, Qt.red)

        self.ball = BallItem(trail_enabled=False, show_velocity=True)
        self.ball.add_to_scene(self.scene)

        # tạo items ban đầu
        self.gfx_left.ensure_items()
        self.gfx_right.ensure_items()

    def sync(self):
        self.gfx_left.sync()
        self.gfx_right.sync()
        b = self.world.ball
        self.ball.sync(b.x, b.y, b.vx, b.vy)
