# tests/test_action_pass_ui.py
from __future__ import annotations
import os, sys, math
from typing import Optional, Tuple

from PyQt5 import uic
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QGraphicsView

from models.world import World
from models.team import Team
from models.robot import Robot
from graphics.scene_manager import SceneManager

# Lấy action & executor từ planning.py
from actions.planning import (
    PlayingAction,
    ActionQValue,
    Location,
    build_move_with_ball_actions,
    choose_best_action,
    can_execute_at,
    exec_pass,
)

DT = 0.050  # 50 ms

def find_graphics_view(ui_root) -> QGraphicsView:
    views = ui_root.findChildren(QGraphicsView)
    if not views:
        raise RuntimeError("Không tìm thấy QGraphicsView trong Interface.ui")
    return views[0]

def setup_world() -> World:
    w = World()
    # chỉ cần 2 robot đỏ, không cần xanh
    w.team_left.ensure_size(0)
    w.team_right.ensure_size(0)

    # Team đỏ tấn công (side="right" trong Team đã có sẵn)
    # Đặt 2 robot: passer (#1) và receiver (#2)
    w.place_robot("right", 1, 6.0, 0.0, math.pi)   # quay về -x
    w.place_robot("right", 2, 0, 1.5, math.pi) 
    
    w.place_robot("right", 3, 4, 1.5, math.pi)  # ở phía trước bên phải

    # Bóng cho #1
    r1 = w.team_right.get(1)
    r1.has_ball = True
    # neo bóng ở mũi robot ngay frame đầu (thế giới sẽ tự neo trong update)
    ax, ay, _, _ = r1.dribble_anchor(ball_radius=w.sticky_ball_radius, gap=w.sticky_gap)
    w.ball.set_pos(ax, ay); w.ball.set_vel(0.0, 0.0)

    w.start()
    return w

def main():
    app = QApplication(sys.argv)

    ui_path = os.path.join(os.path.dirname(__file__), "ui/Interface.ui")
    win = uic.loadUi(ui_path)
    view: QGraphicsView = find_graphics_view(win)

    world = setup_world()
    scene_mgr = SceneManager(world)
    view.setScene(scene_mgr.scene)

    # Ép chỉ cho phép TryToPass đối với passer #1
    allowed = {1: {PlayingAction.TryToPass}}

    # Tạo “sticky rosace” để planner ưu tiên ngay vị trí hiện tại (giúp execute sớm)
    imagined_optimal = {}
    key_pass = 1 * 10000 + PlayingAction.MovingWithBall * 100 + PlayingAction.TryToPass
    r1 = world.team_right.get(1)
    imagined_optimal[key_pass] = ActionQValue(
        imagined_robot_id=1,
        imagined_robot_action=PlayingAction.MovingWithBall,
        action_subtype=PlayingAction.TryToPass,
        action_reward=0.0,
        success_probability=1.0,
        location_action_envisagee=Location(r1.x, r1.y, r1.theta),
        location_action_target_envisagee=None,
        is_current_action_loc=True
    )

    def tick():
        # Xây các điểm rosace cho Pass & chọn action tốt nhất
        actions = build_move_with_ball_actions(
            world,
            world.team_right,
            1,  # passer
            allowed,
            imagined_optimal,
            radius_extended=8.0
        )
        best = choose_best_action(actions)

        # Đồng bộ label debug nếu bạn đã thêm hiển thị trong TeamGraphic
        try:
            r1.dbg_action = "TTPass" if best else "Idle"
        except Exception:
            pass

        if best and best.action_subtype == PlayingAction.TryToPass:
            env = best.location_action_envisagee
            tgt = best.location_action_target_envisagee
            if env:
                # quay mặt về mục tiêu, tiến tới điểm envisagée
                if tgt:
                    r1.command_face_point(tgt.x, tgt.y)
                else:
                    r1.command_face_point(env.x, env.y)
                r1.command_move_towards(env.x, env.y, speed=1.3)

                # đủ gần & hướng đúng -> chuyền thật
                if r1.has_ball and can_execute_at(r1, env):
                    if tgt:
                        exec_pass(world, world.team_right, r1, (tgt.x, tgt.y))
                    else:
                        # fallback: không có target thì chuyền cho #2
                        r2 = world.team_right.get(2)
                        exec_pass(world, world.team_right, r1, (r2.x, r2.y))
        else:
            # fallback: giữ bóng và tiến gần đồng đội
            r2 = world.team_right.get(2)
            r1.command_face_point(r2.x, r2.y)
            r1.command_move_towards(r2.x - 0.3, r2.y, speed=1.0)

        # Vật lý + neo bóng
        world.update(DT)

        # Cập nhật UI
        scene_mgr.sync()

    timer = QTimer(win)
    timer.timeout.connect(tick)
    timer.start(int(DT * 1000))

    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
