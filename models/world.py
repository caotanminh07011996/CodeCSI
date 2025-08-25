# models/world.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Literal, Iterable

from .ball import Ball
from .team import Team

GameState = Literal["stopped", "playing", "kickoff_left", "kickoff_right", "goal", "halt"]


@dataclass
class ScoreBoard:
    left: int = 0
    right: int = 0

    def reset(self) -> None:
        self.left = 0
        self.right = 0


@dataclass
class World:
    """
    Mô hình thế giới MSL (thuần logic):
    - Hệ toạ độ: gốc giữa sân, Ox trái→phải, Oy dưới→trên (m).
    - Quản lý: kích thước sân, bóng, 2 đội (left/right), thời gian, tỉ số, trạng thái trận.
    - TÍCH HỢP: nhận bóng theo 'cone' + hysteresis và dính bóng khi giữ, có cooldown sau sút/chuyền.
    """

    # Kích thước sân (m)
    field_w: float = 22.0
    field_h: float = 14.0

    # Thời gian mô phỏng
    t: float = 0.0

    # Thực thể
    ball: Ball = field(default_factory=Ball)
    team_left: Team = field(default_factory=lambda: Team(team_id=0, name="Blue", side="left", max_size=5))
    team_right: Team = field(default_factory=lambda: Team(team_id=1, name="Red", side="right", max_size=5))

    # Tỉ số & trạng thái
    score: ScoreBoard = field(default_factory=ScoreBoard)
    state: GameState = "stopped"

    # -------- Cấu hình nhận bóng (cone) + dính bóng --------
    cone_dist_on: float = 0.35          # ngưỡng vào cone (bật has_ball)
    cone_angle_on_deg: float = 40.0
    cone_dist_off: float = 0.45         # ngưỡng ra cone (tắt has_ball) — nới lỏng để chống nhấp nháy
    cone_angle_off_deg: float = 60.0

    sticky_enabled: bool = True         # bật/tắt dính bóng
    sticky_ball_radius: float = 0.11    # bán kính bóng (m)
    sticky_gap: float = 0.015           # khe hở giữa mũi robot và bóng (m)
    sticky_clip_field: bool = True      # kẹp bóng trong sân khi dính

    # Cooldown sau khi sút/chuyền: trong thời gian này không ai được bắt bóng lại
    kick_cooldown: float = 0.0          # giây

    # ------------------------------------------------------------
    # Thuộc tính tiện ích
    # ------------------------------------------------------------
    @property
    def half_w(self) -> float:
        return 0.5 * self.field_w

    @property
    def half_h(self) -> float:
        return 0.5 * self.field_h

    def teams(self) -> List[Team]:
        return [self.team_left, self.team_right]

    def all_robots(self) -> Iterable:
        for tm in self.teams():
            yield from tm.robots.values()

    # ------------------------------------------------------------
    # Khởi tạo & bố trí
    # ------------------------------------------------------------
    def ensure_sizes(self, left_n: int = 5, right_n: int = 5) -> None:
        self.team_left.ensure_size(left_n)
        self.team_right.ensure_size(right_n)

    def reset_ball_center(self) -> None:
        self.ball.set_pos(0.0, 0.0)
        self.ball.set_vel(0.0, 0.0)

    def auto_position_kickoff(self) -> None:
        """Xếp đội hình cơ bản 2 đội và đặt bóng giữa sân."""
        self.team_left.auto_position_kickoff(self.field_w, self.field_h)
        self.team_right.auto_position_kickoff(self.field_w, self.field_h)
        self.reset_ball_center()

    def set_kickoff(self, side: Literal["left", "right"]) -> None:
        """Thiết lập trạng thái giao bóng cho đội bên trái/phải."""
        self.state = "kickoff_left" if side == "left" else "kickoff_right"
        self.auto_position_kickoff()

    def start(self) -> None:
        """Bắt đầu chạy mô phỏng (playing)."""
        if self.state.startswith("kickoff"):
            pass
        self.state = "playing"

    def stop(self) -> None:
        self.state = "stopped"

    def halt(self) -> None:
        """Dừng khẩn cấp (giữ nguyên vị trí, tạm dừng thời gian logic)."""
        self.state = "halt"

    def goal_scored(self, by_side: Literal["left", "right"]) -> None:
        """Cập nhật tỉ số và chuyển về trạng thái giao bóng cho đội bị thủng lưới."""
        if by_side == "left":
            self.score.left += 1
            self.set_kickoff("right")
        else:
            self.score.right += 1
            self.set_kickoff("left")

    # ------------------------------------------------------------
    # Cập nhật thời gian
    # ------------------------------------------------------------
    def update(self, dt: float) -> None:
        """
        Thứ tự chuẩn:
          1) Team.update(dt) -> robot
          2) (tuỳ chọn) chống chồng lấn robot
          3) Cập nhật quyền giữ & neo bóng (xem cooldown)
          4) Ball.update(dt) -> bóng bay tự do nếu không bị neo
        """
        if dt <= 0.0:
            return

        # 1) Robot
        self.team_left.update(dt)
        self.team_right.update(dt)

        # 2) Chống chồng lấn (lazy import để tránh vòng import)
        try:
            from simulation.collisions import enforce_no_overlap  # type: ignore
            enforce_no_overlap(self, iterations=6, clearance=0.01, restitution=0.0)
        except Exception:
            pass  # nếu module chưa có hoặc lỗi, bỏ qua

        # 3) Quyền giữ + neo bóng (trước khi ball.update)
        self._update_possession_and_anchor(dt)

        # 4) Bóng
        self.ball.update(dt, field_half_w=self.half_w, field_half_h=self.half_h)

        # 5) Tăng thời gian
        self.t += dt

    # ------------------------------------------------------------
    # Nhận bóng (cone + hysteresis) & dính bóng với cooldown
    # ------------------------------------------------------------
    def _update_possession_and_anchor(self, dt: float) -> None:
        """
        - Giảm kick_cooldown; nếu >0: không ai được bắt bóng, clear has_ball.
        - Nếu hết cooldown: áp dụng hysteresis (on/off) để xác định holder.
        - Nếu sticky_enabled và có holder: neo bóng tại mũi holder (ghi đè pos/vel bóng trước integration).
        """
        # 0) Đếm lùi cooldown
        if self.kick_cooldown > 0.0:
            self.kick_cooldown = max(0.0, self.kick_cooldown - dt)

        bx, by = self.ball.x, self.ball.y

        # Trong thời gian cooldown: không ai giữ bóng
        if self.kick_cooldown > 0.0:
            for tm in self.teams():
                for r in tm.robots.values():
                    r.has_ball = False
            return

        # 1) Giữ người đang có bóng nếu vẫn trong ngưỡng 'off'
        holder = None
        for tm in self.teams():
            for r in tm.robots.values():
                if r.has_ball and r.sees_ball_front(
                    bx, by,
                    max_dist=self.cone_dist_off,
                    half_angle_deg=self.cone_angle_off_deg
                ):
                    holder = r
                    break
            if holder:
                break

        # 2) Nếu chưa có ai giữ, chọn người trong ngưỡng 'on' gần bóng nhất
        if holder is None:
            best_r = None
            best_d2 = float("inf")
            for tm in self.teams():
                for r in tm.robots.values():
                    if not r.active:
                        continue
                    if not r.sees_ball_front(
                        bx, by,
                        max_dist=self.cone_dist_on,
                        half_angle_deg=self.cone_angle_on_deg
                    ):
                        continue
                    d2 = (r.x - bx) ** 2 + (r.y - by) ** 2
                    if d2 < best_d2:
                        best_d2 = d2
                        best_r = r
            holder = best_r

        # 3) Cập nhật cờ has_ball
        for tm in self.teams():
            for r in tm.robots.values():
                r.has_ball = (r is holder)

        # 4) Dính bóng nếu có holder
        if self.sticky_enabled and (holder is not None):
            ax, ay, avx, avy = holder.dribble_anchor(
                ball_radius=self.sticky_ball_radius,
                gap=self.sticky_gap
            )
            if self.sticky_clip_field:
                # kẹp bóng trong sân (trừ bán kính bóng)
                ax = max(-self.half_w + self.sticky_ball_radius, min(self.half_w - self.sticky_ball_radius, ax))
                ay = max(-self.half_h + self.sticky_ball_radius, min(self.half_h - self.sticky_ball_radius, ay))
            self.ball.set_pos(ax, ay)
            self.ball.set_vel(avx, avy)

    def who_has_ball(self) -> Optional[Tuple[Team, int]]:
        """
        Trả về (team, robot_id) đang giữ bóng (dựa vào cờ has_ball).
        Nếu chưa tick nào đặt cờ, trả về None.
        """
        for tm in self.teams():
            for rid, r in tm.robots.items():
                if r.has_ball:
                    return tm, rid
        return None

    # ------------------------------------------------------------
    # Tiện ích đặt nhanh
    # ------------------------------------------------------------
    def place_robot(self, team_side: Literal["left", "right"], robot_id: int,
                    x: float, y: float, theta: float = 0.0) -> None:
        tm = self.team_left if team_side == "left" else self.team_right
        r = tm.get(robot_id)
        if r is None:
            r = tm.add_robot(robot_id=robot_id)
        r.set_pose(x, y, theta)
        r.set_vel(0.0, 0.0, 0.0)
        r.stop()

    def place_ball(self, x: float, y: float, vx: float = 0.0, vy: float = 0.0) -> None:
        self.ball.set_pos(x, y)
        self.ball.set_vel(vx, vy)
