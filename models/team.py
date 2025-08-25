# models/team.py
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Iterable, Tuple, Literal, TYPE_CHECKING

from .robot import Robot  # robot thuần logic (hình vuông cạnh 0.45 m mặc định)

if TYPE_CHECKING:
    from .ball import Ball  # chỉ để type hints, tránh vòng phụ thuộc runtime


Side = Literal["left", "right"]  # "left" = phòng thủ cầu môn x = -11 (tấn công +x)


@dataclass
class Team:
    """
    Quản lý một đội robot (MSL).
    - Hệ tọa độ: gốc giữa sân, Ox trái→phải, Oy dưới→trên (m), theta rad.
    - Team quản lý robot theo TÂM (x,y,theta) — hình học robot (vuông 0.45 m)
      chỉ dùng ở lớp khác (graphics/physics) nếu cần.

    Thuộc tính:
      team_id:   định danh đội (0/1)
      name:      tên hiển thị ("Blue"/"Red"...)
      side:      "left" hoặc "right" (nửa sân phòng thủ)
      max_size:  số robot tối đa (MSL ~ 5)
      robots:    dict[robot_id, Robot]
      goalie_id: robot_id của thủ môn (nếu có)

    Tiện ích:
      add_robot, remove_robot, get
      robots_list(), active_robots()
      update(dt)      -> cập nhật tất cả robot
      nearest_robot_to(x,y), nearest_to_ball(ball)
      auto_position_kickoff(field_w=22, field_h=14)  -> xếp đội hình cơ bản
    """
    team_id: int
    name: str = "Team"
    side: Side = "left"
    max_size: int = 5

    robots: Dict[int, Robot] = field(default_factory=dict)
    goalie_id: Optional[int] = None

    # nội bộ
    _next_robot_id: int = field(default=1, init=False, repr=False)

    # ------------------------------------------------------------
    # Thuộc tính suy diễn
    # ------------------------------------------------------------
    @property
    def attack_sign(self) -> int:
        """Hướng tấn công theo trục Ox: +1 nếu đội ở 'left' (tấn công +x), -1 nếu 'right'."""
        return 1 if self.side == "left" else -1

    @property
    def own_goal_x(self) -> float:
        """Tọa độ x cầu môn nhà."""
        return -11.0 if self.side == "left" else 11.0

    @property
    def opponent_goal_x(self) -> float:
        return 11.0 if self.side == "left" else -11.0

    # ------------------------------------------------------------
    # Quản lý robot
    # ------------------------------------------------------------
    def _alloc_id(self) -> int:
        rid = self._next_robot_id
        self._next_robot_id += 1
        return rid

    def add_robot(self, robot: Optional[Robot] = None, *, robot_id: Optional[int] = None) -> Robot:
        """
        Thêm robot vào đội. Nếu không truyền robot, sẽ tạo Robot mặc định.
        Tự gán team_id & robot_id. Trả về đối tượng Robot.
        """
        if robot is None:
            robot = Robot()
        if robot_id is None:
            robot_id = self._alloc_id()
        else:
            self._next_robot_id = max(self._next_robot_id, robot_id + 1)

        robot.team_id = self.team_id
        robot.robot_id = robot_id
        self.robots[robot_id] = robot

        # nếu chưa có thủ môn, đặt robot đầu tiên làm GK
        if self.goalie_id is None:
            self.goalie_id = robot_id
        return robot

    def remove_robot(self, robot_id: int) -> None:
        self.robots.pop(robot_id, None)
        if self.goalie_id == robot_id:
            self.goalie_id = next(iter(self.robots.keys()), None)

    def get(self, robot_id: int) -> Optional[Robot]:
        return self.robots.get(robot_id)

    def robots_list(self) -> List[Robot]:
        return [self.robots[rid] for rid in sorted(self.robots.keys())]

    def active_robots(self) -> Iterable[Robot]:
        return (r for r in self.robots_list() if r.active)

    def set_active(self, robot_id: int, flag: bool) -> None:
        r = self.get(robot_id)
        if r:
            r.active = bool(flag)

    def set_goalie(self, robot_id: int) -> None:
        if robot_id in self.robots:
            self.goalie_id = robot_id

    # ------------------------------------------------------------
    # Cập nhật/tiện ích
    # ------------------------------------------------------------
    def update(self, dt: float) -> None:
        """Cập nhật tất cả robot theo thời gian dt."""
        for r in self.robots.values():
            r.update(dt)

    def center_of_mass(self) -> Tuple[float, float]:
        """Tâm hình học của các robot (trung bình vị trí)."""
        lst = self.robots_list()
        if not lst:
            return (0.0, 0.0)
        sx = sum(r.x for r in lst)
        sy = sum(r.y for r in lst)
        n = float(len(lst))
        return (sx / n, sy / n)

    def nearest_robot_to(self, x: float, y: float, *, active_only: bool = True) -> Optional[Robot]:
        """Trả về robot gần (x,y) nhất."""
        best: Optional[Robot] = None
        best_d2 = float("inf")
        for r in (self.active_robots() if active_only else self.robots_list()):
            dx, dy = r.x - x, r.y - y
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2 = d2
                best = r
        return best

    def nearest_to_ball(self, ball: Ball, *, active_only: bool = True) -> Optional[Robot]:
        return self.nearest_robot_to(ball.x, ball.y, active_only=active_only)

    # ------------------------------------------------------------
    # Đội hình & auto-position
    # ------------------------------------------------------------
    def ensure_size(self, n: int) -> None:
        """
        Bảo đảm đội có đúng n robot (>=1). Thêm bớt robot mặc định nếu cần.
        """
        n = max(1, int(n))
        current = len(self.robots)
        if current < n:
            for _ in range(n - current):
                self.add_robot()
        elif current > n:
            # Xóa các robot id lớn nhất trước
            for rid in sorted(self.robots.keys(), reverse=True)[: current - n]:
                self.remove_robot(rid)

    def auto_position_kickoff(
        self,
        field_w: float = 22.0,
        field_h: float = 14.0,
        margin_goal: float = 0.5,
    ) -> None:
        """
        Xếp đội hình “kick-off” cơ bản theo nửa sân phòng thủ:
        - GK gần cầu môn nhà
        - 1 hậu vệ lùi
        - 2 tiền vệ rộng (±y)
        - 1 tiền đạo
        Hướng quay mặt về phía tấn công.
        """
        half_w = field_w * 0.5
        half_h = field_h * 0.5
        s = self.attack_sign  # +1 (tấn công +x) hoặc -1

        # toạ độ x cơ bản (tính theo hướng tấn công, rồi dịch theo side)
        x_gk = -s * (half_w - margin_goal)             # gần khung thành nhà
        x_def = -s * 6.0
        x_mid = -s * 3.0
        x_fwd = -s * 1.0

        # toạ độ y
        y0 = 0.0
        y_mid = 2.0
        y_max = half_h - 0.5

        # đảm bảo không vượt biên
        def clip_xy(x: float, y: float) -> Tuple[float, float]:
            x = max(-half_w + 0.1, min(half_w - 0.1, x))
            y = max(-half_h + 0.1, min(half_h - 0.1, y))
            return (x, y)

        # góc quay: hướng về khung thành đối phương
        face_theta = 0.0 if s == 1 else math.pi

        # danh sách robot theo thứ tự: GK, DF, MF1, MF2, FW (cắt bớt nếu thiếu)
        order = self.robots_list()
        if not order:
            self.ensure_size(self.max_size)
            order = self.robots_list()

        # Bảo đảm GK ở vị trí đầu tiên trong order (nếu có goalie_id)
        if self.goalie_id is not None:
            order.sort(key=lambda r: (0 if r.robot_id == self.goalie_id else 1, r.robot_id))
        else:
            # đặt robot đầu tiên làm GK nếu chưa có
            self.goalie_id = order[0].robot_id

        # tạo mẫu vị trí theo số robot hiện có
        templates: List[Tuple[float, float]] = []
        n = len(order)
        if n >= 1:
            templates.append((x_gk, y0))
        if n >= 2:
            templates.append((x_def, y0))
        if n >= 3:
            templates.append((x_mid, +y_mid))
        if n >= 4:
            templates.append((x_mid, -y_mid))
        if n >= 5:
            templates.append((x_fwd, 0.0))
        # nếu >5, rải thêm dọc theo trục y quanh x_mid
        extra = n - len(templates)
        if extra > 0:
            step = max(1.0, y_max / (extra + 1))
            for i in range(extra):
                templates.append((x_mid, (i + 1) * step * (-1 if i % 2 else 1)))

        # đặt pose cho từng robot
        for r, (px, py) in zip(order, templates):
            px, py = clip_xy(px, py)
            r.set_pose(px, py, face_theta)
            r.set_vel(0.0, 0.0, 0.0)
            r.stop()

    # ------------------------------------------------------------
    # Tiện ích debug/hiển thị
    # ------------------------------------------------------------
    def __repr__(self) -> str:
        side = self.side
        players = ", ".join(f"{r.robot_id}@({r.x:.1f},{r.y:.1f})" for r in self.robots_list())
        return f"Team#{self.team_id}({self.name}, side={side}, GK={self.goalie_id}): [{players}]"
