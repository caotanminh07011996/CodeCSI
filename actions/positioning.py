# actions/positioning.py
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional
from .base import Action, Status
from models.world import World
from models.team import Team
from models.robot import Robot

def _sign(team: Team) -> int:
    return +1 if team.side=="left" else -1

def _clamp(x, lo, hi): return max(lo, min(hi, x))

def _wrap(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi

def distorted_theoretical_xy(world: World, team: Team, x: float, y: float,
                             distort_k: float = 0.35) -> tuple[float, float]:
    """
    'Distort' theo chiều tấn công: càng gần cầu môn đối phương, giới hạn
    biên mạnh tay hơn để tránh dồn ra biên/góc.
    """
    s = _sign(team)
    # hệ số nén theo khoảng cách tới biên đối phương
    t = (x * s + world.half_w) / (2*world.half_w)    # ~[0..1]
    k = 1.0 - distort_k * t                          # 1 → (1-distort_k)
    max_y = k * (world.half_h - 0.5)
    return (_clamp(x, -world.half_w+0.5, world.half_w-0.5),
            _clamp(y, -max_y, max_y))

def kickoff_restricted(world: World, team: Team, x: float, y: float) -> tuple[float, float]:
    """
    Hạn chế kickoff tối giản:
     - Không đứng trong vòng tròn giữa sân bán kính 1.0 khi *đối thủ* giao bóng.
     - Giữ trong phần sân của mình trước khi 'playing'.
    """
    st = world.state
    x2, y2 = x, y

    # giữ về nửa sân mình nếu chưa 'playing'
    if st != "playing":
        s = _sign(team)
        if s == +1:  # left tấn công +x → nửa trái là x <= 0
            x2 = min(x2, 0.0)
        else:        # right → nửa phải
            x2 = max(x2, 0.0)

    # vòng tròn giữa sân
    if st in ("kickoff_left", "kickoff_right"):
        cx, cy, r = 0.0, 0.0, 1.0
        if (x2-cx)**2 + (y2-cy)**2 < r*r:
            # đẩy ra biên vòng tròn theo hướng giữ nguyên góc
            ang = math.atan2(y2-cy, x2-cx)
            x2 = cx + r * math.cos(ang)
            y2 = cy + r * math.sin(ang)

    return x2, y2

# ---------------- Actions ----------------

@dataclass(slots=True)
class PositioningPlayingBall(Action):
    """
    Vị trí hỗ trợ người cầm bóng: đứng 'sau bóng' theo hướng khung thành đối phương,
    tạo góc chuyền an toàn (offset_y).
    """
    offset_back: float = 1.2
    offset_side: float = 0.8
    speed: float = 1.6
    stop_dist: float = 0.15

    def __post_init__(self): self.name = "PositioningPlayingBall"

    def step(self, world: World, team: Team, robot: Robot, dt: float) -> Status:
        bx, by = world.ball.x, world.ball.y
        s = _sign(team)
        # điểm lý thuyết: sau bóng theo trục tấn công, lệch y
        tx = bx - s * self.offset_back
        ty = by + (self.offset_side if by <= 0 else -self.offset_side)
        tx, ty = distorted_theoretical_xy(world, team, tx, ty)
        tx, ty = kickoff_restricted(world, team, tx, ty)
        robot.command_face_point(bx, by)
        robot.command_move_towards(tx, ty, speed=self.speed)
        if (robot.x-tx)**2 + (robot.y-ty)**2 <= self.stop_dist**2:
            return Status.SUCCESS
        return Status.RUNNING

@dataclass(slots=True)
class PositioningAssist(Action):
    """
    Mở đường chuyền: tạo tam giác với người cầm bóng và cầu môn đối phương.
    """
    radial: float = 2.5
    angle_deg: float = 35
    speed: float = 1.6
    stop_dist: float = 0.2

    def __post_init__(self): self.name = "PositioningAssist"

    def step(self, world: World, team: Team, robot: Robot, dt: float) -> Status:
        bx, by = world.ball.x, world.ball.y
        s = _sign(team)
        goal_x = world.half_w if s>0 else -world.half_w
        # hướng từ bóng tới goal, xoay ±angle để mở tuyến chuyền
        ang = math.atan2(0.0 - by, goal_x - bx)
        ang += math.radians(self.angle_deg if (robot.robot_id % 2)==0 else -self.angle_deg)
        tx = bx + self.radial * math.cos(ang)
        ty = by + self.radial * math.sin(ang)
        tx, ty = distorted_theoretical_xy(world, team, tx, ty)
        tx, ty = kickoff_restricted(world, team, tx, ty)
        robot.command_face_point(bx, by)
        robot.command_move_towards(tx, ty, speed=self.speed)
        if (robot.x-tx)**2 + (robot.y-ty)**2 <= self.stop_dist**2:
            return Status.SUCCESS
        return Status.RUNNING

@dataclass(slots=True)
class PositioningDefense(Action):
    """
    Phòng ngự: đứng trên đường nối BÓNG → CẦU MÔN MÌNH, ở giữa và cách bóng 'depth'.
    """
    depth: float = 2.5
    speed: float = 1.6
    stop_dist: float = 0.2

    def __post_init__(self): self.name = "PositioningDefense"

    def step(self, world: World, team: Team, robot: Robot, dt: float) -> Status:
        s = _sign(team)
        goal_x = -world.half_w if s>0 else world.half_w
        bx, by = world.ball.x, world.ball.y
        ang = math.atan2(by - 0.0, bx - goal_x)  # từ goal về bóng
        # lùi 'depth' từ bóng về phía gôn mình
        tx = bx - self.depth * math.cos(ang)
        ty = by - self.depth * math.sin(ang)
        tx, ty = distorted_theoretical_xy(world, team, tx, ty)
        tx, ty = kickoff_restricted(world, team, tx, ty)
        robot.command_face_point(bx, by)
        robot.command_move_towards(tx, ty, speed=self.speed)
        if (robot.x-tx)**2 + (robot.y-ty)**2 <= self.stop_dist**2:
            return Status.SUCCESS
        return Status.RUNNING

@dataclass(slots=True)
class GoalKeeping(Action):
    """
    Thủ môn cơ bản: bám theo y của bóng trên trục khung thành, giới hạn trong miệng gôn.
    """
    line_depth: float = 0.4
    speed: float = 1.8
    tol_y: float = 0.12

    def __post_init__(self): self.name = "GoalKeeping"

    def step(self, world: World, team: Team, robot: Robot, dt: float) -> Status:
        from config.constants import GOAL_WIDTH
        s = _sign(team)
        xg = -world.half_w + self.line_depth if s>0 else world.half_w - self.line_depth
        yg = _clamp(world.ball.y, -GOAL_WIDTH*0.5, GOAL_WIDTH*0.5)
        robot.command_face_point(world.ball.x, world.ball.y)
        robot.command_move_towards(xg, yg, speed=self.speed)
        if abs(robot.y - yg) <= self.tol_y and abs(robot.x - xg) <= 0.1:
            return Status.SUCCESS
        return Status.RUNNING


@dataclass(slots=True)
class SeekBall(Action):
    """
    Lao tới bóng và 'bắt' bóng khi đủ gần & nằm trong nón phía trước.
    Khi bắt thành công: gắn bóng vào mặt trước robot (dính bóng).
    """
    approach_speed: float = 1.8
    capture_dist: float = 0.35
    front_cone_deg: float = 45.0
    glue_epsilon: float = 0.01

    def __post_init__(self):
        self.name = "SeekBall"

    def step(self, world: World, team: Team, robot: Robot, dt: float) -> Status:
        bx, by = world.ball.x, world.ball.y

        # điều khiển: quay mặt & tiến tới bóng
        robot.command_face_point(bx, by)
        robot.command_move_towards(bx, by, speed=self.approach_speed)

        # điều kiện bắt bóng
        dx, dy = bx - robot.x, by - robot.y
        d = math.hypot(dx, dy)
        ang_to_ball = math.atan2(dy, dx)
        if d <= self.capture_dist and abs(_wrap(ang_to_ball - robot.theta)) <= math.radians(self.front_cone_deg):
            robot.has_ball = True
            # dính bóng phía trước mũi robot
            dfront = robot.half_side + world.ball.radius - self.glue_epsilon
            c, s = math.cos(robot.theta), math.sin(robot.theta)
            world.ball.set_pos(robot.x + dfront * c, robot.y + dfront * s)
            world.ball.set_vel(robot.vx, robot.vy)
            return Status.SUCCESS

        return Status.RUNNING
