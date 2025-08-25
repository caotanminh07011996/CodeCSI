from __future__ import annotations
import os, sys, math
from typing import Optional, Tuple, List

# ---------- Qt ----------
from PyQt5 import uic
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QGraphicsView

# ---------- core world & strategy ----------
from models.world import World
from models.robot import Robot
from controllers.strategy_planner_full import StrategyPlannerFull

# ---------- your graphics glue ----------
from graphics.scene_manager import SceneManager  # wraps FieldDrawer + TeamGraphic + BallItem

DT = 0.050  # 50 ms

# --- small helpers for "glue" ball when controlled ---
BALL_R = 0.11
GLUE_EPS = 0.01
CATCH_DIST = 0.28
CONE_HALF_DEG = 42.0

def _wrap(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi

def _ang(ax, ay, bx, by) -> float:
    return math.atan2(by - ay, bx - ax)

def attach_ball(world: World, r: Robot) -> None:
    d = r.half_side + BALL_R - GLUE_EPS
    c, s = math.cos(r.theta), math.sin(r.theta)
    world.ball.set_pos(r.x + d * c, r.y + d * s)
    world.ball.set_vel(r.vx, r.vy)

def try_auto_catch(world: World) -> Optional[Tuple[str, int]]:
    bx, by = world.ball.x, world.ball.y
    for side, tm in (("left", world.team_left), ("right", world.team_right)):
        for rid, r in tm.robots.items():
            if not r.active: continue
            d = math.hypot(bx - r.x, by - r.y)
            if d > CATCH_DIST: continue
            ang = _ang(r.x, r.y, bx, by)
            if abs(_wrap(ang - r.theta)) <= math.radians(CONE_HALF_DEG):
                r.has_ball = True
                attach_ball(world, r)
                return (side, rid)
    return None

def get_holder(team) -> Optional[int]:
    for rid, r in team.robots.items():
        if r.active and r.has_ball: return rid
    return None

# --- initial layout: Blue defend (left), Red attack (right) ---
def setup_world() -> World:
    w = World(); w.ensure_sizes(5, 5)
    # Blue (left, defend)
    w.place_robot("left", 1, -w.half_w + 0.6, 0.0, 0.0)  # GK-ish
    w.place_robot("left", 2, -7.5, -2.0, 0.0)
    w.place_robot("left", 3, -7.5,  2.0, 0.0)
    w.place_robot("left", 4, -5.0,  0.0, 0.0)
    w.place_robot("left", 5, -6.0,  3.0, 0.0)

    # Red (right, attack)
    w.place_robot("right", 1,  7.5, 0.5, math.pi)       # holder
    w.place_robot("right", 2,  8.5, -2.0, math.pi*0.90)
    w.place_robot("right", 3,  9.0,  2.0, math.pi*1.05)
    w.place_robot("right", 4,  6.5,  0.0, math.pi)
    w.place_robot("right", 5,  6.0,  3.0, math.pi)

    # give ball to red #1
    r1 = w.team_right.get(1); r1.has_ball = True
    attach_ball(w, r1)

    w.start()
    return w

def find_graphics_view(ui_root) -> QGraphicsView:
    # Lấy QGraphicsView đầu tiên trong .ui (không cần biết objectName)
    views = ui_root.findChildren(QGraphicsView)
    if not views:
        raise RuntimeError("Không tìm thấy QGraphicsView trong Interface.ui")
    return views[0]

def main():
    app = QApplication(sys.argv)

    # 1) Load UI
    ui_path = os.path.join(os.path.dirname(__file__), "ui/Interface.ui")
    win = uic.loadUi(ui_path)
    view: QGraphicsView = find_graphics_view(win)

    # 2) World + planners
    world = setup_world()
    red_planner  = StrategyPlannerFull(team_side="right", primary_attacker_id=1)
    blue_planner = StrategyPlannerFull(team_side="left",  primary_attacker_id=1)

    # 3) SceneManager (sân + team + bóng). SceneManager đã:
    #    - FieldDrawer().draw(scene)
    #    - tạo TeamGraphic(left/right) & BallItem, rồi sync() mỗi frame.
    sm = SceneManager(world)  # tạo sẵn scene và các items  :contentReference[oaicite:1]{index=1}
    view.setScene(sm.scene)

    # 4) Timer tick: chiến thuật → vật lý → sync đồ hoạ
    def tick():
        red_planner.decide(world)
        blue_planner.decide(world)

        # giữ dính bóng hoặc bắt bóng lại nếu tự do
        red_holder  = get_holder(world.team_right)
        blue_holder = get_holder(world.team_left)
        if red_holder is not None:
            attach_ball(world, world.team_right.get(red_holder))
        elif blue_holder is not None:
            attach_ball(world, world.team_left.get(blue_holder))
        else:
            try_auto_catch(world)

        world.update(DT)
        sm.sync()  # gọi TeamGraphic.sync() + BallItem.sync(vx,vy) bên trong  

    timer = QTimer(win)
    timer.timeout.connect(tick)
    timer.start(int(DT * 1000))

    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
