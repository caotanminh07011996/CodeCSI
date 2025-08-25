# actions/planning.py
from __future__ import annotations

import math, random
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Iterable
from enum import IntEnum

from models.world import World
from models.team import Team
from models.robot import Robot

# ===== Enums & datatypes =====

class PlayingAction(IntEnum):
    NoneAction = 0
    MovingWithBall = 1           # Long action
    TryToShoot = 2               # Short (instant)
    TryToPass = 3
    TryToDeepPass = 4
    TryToDribble = 5
    Positioning = 6
    PositioningPlayingBall = 7
    PositioningAssist = 8
    PositioningDefense = 9
    PositioningStrategyFixed = 10
    GoalKeeping = 11
    Goto = 12

@dataclass
class Location:
    x: float
    y: float
    theta: float = 0.0

@dataclass
class ActionQValue:
    imagined_robot_id: int
    imagined_robot_action: int                     # PlayingAction (long)
    action_subtype: Optional[int] = None           # PlayingAction (short)
    action_reward: float = 0.0
    success_probability: float = 1.0
    location_action_envisagee: Optional[Location] = None
    location_action_target_envisagee: Optional[Location] = None
    is_current_action_loc: bool = False            # flag cho điểm “đang theo”

    def set_envisagee(self, loc: Location) -> None:
        self.location_action_envisagee = loc

    def set_target(self, loc: Location) -> None:
        self.location_action_target_envisagee = loc


# ===== Tham số thực thi =====
EXEC_DIST = 0.20            # m: phải tới gần điểm envisagée mới bắn/chuyền
EXEC_ANG_DEG = 25.0         # độ: sai số hướng cho phép khi bắn/chuyền (nới lỏng)
PASS_SPEED = 6.0            # m/s
SHOT_SPEED = 7.5            # m/s
OPP_MAX_SPEED = 2.5         # m/s (giả định đối thủ tối đa)
BALL_RADIUS = 0.11          # m (size 5 ~ đường kính 0.22)

def _angle_wrap(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi

def can_execute_at(robot: Robot, target: Location,
                   pos_tol: float = EXEC_DIST, ang_tol_deg: float = EXEC_ANG_DEG) -> bool:
    """Robot đã ở gần điểm envisagée & quay đúng hướng chưa?"""
    if math.hypot(robot.x - target.x, robot.y - target.y) > pos_tol:
        return False
    err = _angle_wrap(target.theta - robot.theta)
    return abs(err) <= math.radians(ang_tol_deg)

def _place_ball_in_front(robot: Robot, gap: float = 0.02) -> Tuple[float, float]:
    """Đặt bóng ngay trước mũi robot (tránh kẹt trong thân) theo hướng robot."""
    front = robot.half_side + BALL_RADIUS + gap
    return (robot.x + math.cos(robot.theta) * front,
            robot.y + math.sin(robot.theta) * front)

def _set_cooldown(world: World, seconds: float) -> None:
    """Đặt cooldown bắt bóng nếu World có thuộc tính này."""
    if hasattr(world, "kick_cooldown"):
        setattr(world, "kick_cooldown", float(seconds))

def exec_shoot(world: World, team: Team, robot: Robot,
               speed: float = SHOT_SPEED) -> None:
    """Sút thật: thả bóng ra trước mũi rồi đặt vận tốc về phía cầu môn đối phương."""
    # 1) thả bóng ra trước mũi & bỏ quyền giữ
    bx, by = _place_ball_in_front(robot)
    world.ball.set_pos(bx, by)
    robot.has_ball = False

    # 2) hướng tới khung thành đối phương (y=0)
    goal_x = world.half_w if team.side == "left" else -world.half_w
    ang = math.atan2(0.0 - by, goal_x - bx)

    # 3) đặt vận tốc bóng
    if hasattr(world.ball, "kick"):
        world.ball.kick(speed, ang)
    else:
        world.ball.set_vel(speed * math.cos(ang), speed * math.sin(ang))

    # 4) cooldown để không bắt lại ngay
    _set_cooldown(world, 0.25)

def exec_pass(world: World, team: Team, robot: Robot,
              to_xy: Tuple[float, float], speed: float = PASS_SPEED) -> None:
    """Chuyền thật: thả bóng ra trước mũi rồi đặt vận tốc hướng tới to_xy."""
    bx, by = _place_ball_in_front(robot)
    world.ball.set_pos(bx, by)
    robot.has_ball = False

    tx, ty = to_xy
    ang = math.atan2(ty - by, tx - bx)
    if hasattr(world.ball, "kick"):
        world.ball.kick(speed, ang)
    else:
        world.ball.set_vel(speed * math.cos(ang), speed * math.sin(ang))

    _set_cooldown(world, 0.25)


# ===== Rosace generator (DetermineActionPossibleLocations) =====
def determine_action_possible_locations(
    base_location: Location,
    rosace_location: Optional[Location],
    radius: float,
    nb_pts_test_base: int = 5,
    nb_pts_test_rosace: int = 3,
    rosace_small_radii: Iterable[float] = (0.2,)
) -> List[Tuple[Location, bool]]:
    """
    Trả về danh sách [(Location, is_current)]:
    - Rải ngẫu nhiên nb_pts_test_base điểm quanh base_location trong bán kính ~radius
    - Nếu có rosace_location: thêm chính nó (is_current=True) và 1 vòng nhỏ nb_pts_test_rosace xung quanh
    """
    pts: List[Tuple[Location, bool]] = []

    # Vòng base (random jitter)
    for _ in range(nb_pts_test_base):
        x = base_location.x + (random.random() - 0.5) * radius
        y = base_location.y + (random.random() - 0.5) * radius
        pts.append((Location(x, y, 0.0), False))

    if rosace_location is not None:
        # điểm “đang theo”
        pts.append((Location(rosace_location.x, rosace_location.y, rosace_location.theta), True))

        # vòng nhỏ quanh rosace_location
        for r_small in rosace_small_radii:
            for k in range(max(1, nb_pts_test_rosace)):
                ang = (2.0 * math.pi * k / max(1, nb_pts_test_rosace)) \
                      + (random.random() - 0.5) * (math.pi / max(1, nb_pts_test_rosace))
                dist = r_small + (random.random() - 0.5) * r_small
                x = rosace_location.x + dist * math.cos(ang)
                y = rosace_location.y + dist * math.sin(ang)
                pts.append((Location(x, y, rosace_location.theta), False))

    return pts


# ===== Heuristics & geometry helpers =====
def _attack_sign(team: Team) -> int:
    return +1 if team.side == "left" else -1

def _goal_x_for(team: Team, world: World) -> float:
    return world.half_w if team.side == "left" else -world.half_w

def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])

def _nearest_opponent_dist(world: World, team: Team, x: float, y: float) -> float:
    best = float("inf")
    opp = world.team_right if team.side == "left" else world.team_left
    for r in opp.robots.values():
        if not r.active:
            continue
        d = _dist((x, y), (r.x, r.y))
        if d < best:
            best = d
    return best

def _seg_point_distance(p0: Tuple[float, float], p1: Tuple[float, float], p: Tuple[float, float]) -> Tuple[float, float]:
    x0, y0 = p0; x1, y1 = p1; x, y = p
    vx, vy = x1 - x0, y1 - y0
    L2 = vx * vx + vy * vy
    if L2 <= 1e-12:
        return math.hypot(x - x0, y - y0), 0.0
    t = ((x - x0) * vx + (y - y0) * vy) / L2
    t = max(0.0, min(1.0, t))
    proj = (x0 + t * vx, y0 + t * vy)
    return math.hypot(x - proj[0], y - proj[1]), t

def ray_clearance_metric(world: World, team: Team,
                         p0: Tuple[float, float], p1: Tuple[float, float],
                         safety: float = 0.30) -> Tuple[float, float]:
    opp = world.team_right if team.side == "left" else world.team_left
    min_d = float("inf")
    covered_spans = 0
    L = max(1e-6, math.hypot(p1[0] - p0[0], p1[1] - p0[1]))
    for o in opp.robots.values():
        if not o.active:
            continue
        d, t = _seg_point_distance(p0, p1, (o.x, o.y))
        if d < min_d:
            min_d = d
        if 0.0 <= t <= 1.0 and d <= safety:
            covered_spans += 1
    cover = min(1.0, covered_spans * (0.6 / (L + 0.1)))
    if min_d == float("inf"):
        min_d = L
    return (min_d, cover)


# ===== Scoring =====
def evaluate_shoot(world: World, team: Team, shoot_pos: Location,
                   goal_y: float, respect_3m: bool, robot_start: Location) -> Tuple[float, float]:
    """
    Port từ C#: reward & success_prob của cú sút, gồm:
      - Xác suất di chuyển tới điểm sút không bị cắt (teammate vs opponent)
      - Xác suất cú sút không bị cắt (ball vs opponent)
      - Phạt/ thưởng theo 3m, quãng đường chuẩn bị, và mở góc cầu môn
      - Cấm sút từ nửa sân nhà
    """
    sign = _attack_sign(team)
    goal_x = _goal_x_for(team, world)

    # --- base reward: giống C#: teamStrategyParameters.BaseRewardShoot ~ 1.0
    reward = 1.0
    prob = 1.0

    # --- proba di chuyển tới điểm sút không bị cắt
    opp = world.team_right if team.side == "left" else world.team_left
    interceptors = [(o.x, o.y) for o in opp.robots.values() if o.active]

    p_move = evaluate_success_probability_absence_interception(
        (robot_start.x, robot_start.y), (shoot_pos.x, shoot_pos.y),
        interceptors, vitesse_deplacement=3.0, opponent_max_speed=3.0,
        inter_centre_distance=0.55, temps_reaction_opponent=0.1
    )
    prob *= p_move

    # --- proba cú sút không bị cắt
    p_shot = evaluate_success_probability_absence_interception(
        (shoot_pos.x, shoot_pos.y), (goal_x, goal_y),
        interceptors, vitesse_deplacement=15.0, opponent_max_speed=3.0,
        inter_centre_distance=0.40, temps_reaction_opponent=0.1
    )
    prob *= p_shot

    # --- rule 3m: giảm reward nếu mang bóng quá 3m trước khi sút
    d_carry = _dist((robot_start.x, robot_start.y), (shoot_pos.x, shoot_pos.y))
    reward *= linear_in_interval(d_carry, 2.5, 3.0, 1.0, 0.0)

    # --- thưởng/phạt theo quãng chuẩn bị (0..3m)
    reward *= linear_in_interval(d_carry, 0.0, 3.0, 1.0, 0.8)

    # --- mở góc cầu môn (0.5..1.0)
    reward *= evaluate_goal_opening_angle(world, team, shoot_pos)

    # --- không cho sút từ nửa sân nhà
    if shoot_pos.x * sign <= 0.0:
        reward = 0.0

    # --- ràng buộc & trả về
    return (max(0.0, reward), max(0.0, min(1.0, prob)))


def evaluate_pass(world: World, team: Team, pass_from: Location, teammate: Robot) -> Tuple[float, float]:
    p0 = (pass_from.x, pass_from.y)
    p1 = (teammate.x, teammate.y)
    d = _dist(p0, p1)
    space = _nearest_opponent_dist(world, team, teammate.x, teammate.y)

    min_d, cover = ray_clearance_metric(world, team, p0, p1, safety=0.30)
    t_ball = d / max(1e-6, PASS_SPEED)
    t_opp = min_d / max(1e-6, OPP_MAX_SPEED)
    cut_prob = max(0.0, 1.0 - (t_opp / (t_ball + 1e-6)))

    range_bonus = max(0.0, 1.0 - d / 10.0)
    space_bonus = min(space / 2.0, 1.0)
    base_p = 0.5 * range_bonus + 0.5 * space_bonus
    p = max(0.05, base_p * (1.0 - 0.9 * cover) * (1.0 - 0.8 * cut_prob))

    reward = 2.2 * range_bonus + 2.8 * space_bonus - 1.5 * (1.0 - min(1.0, min_d / 0.6))
    return (max(0.0, reward), max(0.0, min(1.0, p)))

def evaluate_dribble(world: World, team: Team, from_loc: Location, to_loc: Location) -> Tuple[float, float]:
    progress = _attack_sign(team) * (to_loc.x - from_loc.x)
    space = _nearest_opponent_dist(world, team, to_loc.x, to_loc.y)
    reward = 0.8 * progress + 1.2 * min(space, 2.0)
    p = max(0.1, min(1.0, space / 2.0))
    return (max(0.0, reward), p)

def evaluate_deep_pass(world: World, team: Team, pass_from: Location,
                       receive_at: Location, shoot_goal_y: float) -> Tuple[float, float]:
    r_pass, p_pass = evaluate_pass(
        world, team, pass_from,
        type("T", (), {"x": receive_at.x, "y": receive_at.y, "active": True})()
    )
    r_shoot, p_shoot = evaluate_shoot(world, team, receive_at, shoot_goal_y, respect_3m=False, robot_start=pass_from)
    reward = 0.5 * r_pass + 0.8 * r_shoot
    p = p_pass * p_shoot
    return (max(0.0, reward), max(0.0, min(1.0, p)))

##### helper###########################


def _angle(a: tuple[float, float], b: tuple[float, float]) -> float:
    # góc của vector a->b
    (x0, y0), (x1, y1) = a, b
    return math.atan2(y1 - y0, x1 - x0)

def _angle_abs_diff(a: float, b: float) -> float:
    # |diff| với wrap về [-pi, pi]
    d = (a - b + math.pi) % (2.0 * math.pi) - math.pi
    return abs(d)



def linear_in_interval(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if x <= x0: return y0
    if x >= x1: return y1
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

def evaluate_success_probability_absence_interception(
    start: Tuple[float, float],
    cible: Tuple[float, float],
    interceptors: Iterable[Tuple[float, float]],
    vitesse_deplacement: float,         # tốc độ “bên mình”: bóng/robot tuỳ ngữ cảnh
    opponent_max_speed: float,          # tốc độ tối đa đối thủ
    inter_centre_distance: float = 0.35,
    temps_reaction_opponent: float = 0.1
) -> float:
    """
    Port từ C#: với mỗi đối thủ, lấy hình chiếu gần nhất lên đoạn start->cible.
    So sánh thời gian đối thủ tới điểm đó (cộng thời gian phản ứng) với thời gian
    của bóng/robot tới cùng điểm. Lấy tỉ lệ min, rồi nội suy [0.8..1.0] -> [0..1].
    """
    sx, sy = start
    cx, cy = cible
    vx, vy = cx - sx, cy - sy
    L = math.hypot(vx, vy)
    if L <= 1e-9:
        return 1.0

    crits: List[float] = []
    for (ix, iy) in interceptors:
        # khoảng cách & tham số t tới đoạn
        d, t = _seg_point_distance(start, cible, (ix, iy))  # đã có sẵn ở file của bạn
        d_eff = max(0.0, d - inter_centre_distance)
        tr = 0.0 if d_eff == 0.0 else temps_reaction_opponent
        t_opp = d_eff / max(1e-6, opponent_max_speed) + tr

        # quãng đường từ start tới điểm chiếu
        d_start_proj = t * L
        t_ball = d_start_proj / max(1e-6, vitesse_deplacement)

        crits.append(t_opp / max(1e-6, t_ball))

    if not crits:
        return 1.0
    crit_final = min(crits)
    # C#: LinearInInterval(minRatio, 0.8, 1.0, 0, 1)
    return linear_in_interval(crit_final, 0.8, 1.0, 0.0, 1.0)



def evaluate_goal_opening_angle(world, team, target_pos, goal_half_height: float = 1.2) -> float:
    """
    Port từ C# Evaluate_GoalOpeningAngle:
    - Lấy 2 góc nhìn tới 2 mép khung thành: (goal_x, ±goal_half_height)
    - Độ mở = |diff góc| (đã wrap), rồi nội suy [0 .. pi/3] -> [0.2 .. 1.0]
    """
    # toạ độ cột dọc khung thành đối phương
    goal_x = world.half_w if team.side == "left" else -world.half_w
    tx, ty = target_pos.x, target_pos.y

    hi = _angle((tx, ty), (goal_x, +goal_half_height))
    lo = _angle((tx, ty), (goal_x, -goal_half_height))
    opening = _angle_abs_diff(hi, lo)           # tương đương C#: Abs(high - Modulo2PiAroundAngle(high, low))

    # ánh xạ giống C#: LinearInInterval(opening, 0, PI/3, 0.2, 1)
    return linear_in_interval(opening, 0.0, math.pi / 3.0, 0.2, 1.0)

# ===== Planner: MovingWithBall → build instant actions via rosace =====
def build_move_with_ball_actions(
    world: World,
    team: Team,
    robot_id: int,
    team_possible_actions: Dict[int, set[int]],
    imagined_optimal_long_actions: Dict[int, ActionQValue],
    *,
    radius_extended: float = 11.0
) -> List[ActionQValue]:
    r = team.get(robot_id)
    if r is None:
        return []
    goal_x = _goal_x_for(team, world)
    sign = _attack_sign(team)

    def _key(sub: int) -> int:
        return robot_id * 10000 + PlayingAction.MovingWithBall * 100 + sub

    default_types = [PlayingAction.TryToShoot, PlayingAction.TryToPass,
                     PlayingAction.TryToDeepPass, PlayingAction.TryToDribble]
    allowed = team_possible_actions.get(robot_id, set(default_types))
    instant_types = [a for a in default_types if a in allowed]

    results: List[ActionQValue] = []

    for inst in instant_types:
        ref = imagined_optimal_long_actions.get(_key(inst))
        rosace_loc = ref.location_action_envisagee if (ref and ref.location_action_envisagee) else None

        possible: List[Tuple[Location, bool]] = []
        if inst == PlayingAction.TryToShoot:
            base_pos = Location(sign * world.field_w / 4.0, 0.0, 0.0)
            aa = determine_action_possible_locations(base_pos, rosace_loc, radius=10.0, nb_pts_test_base=4, nb_pts_test_rosace=4)
            bb = determine_action_possible_locations(Location(r.x, r.y, r.theta), None, radius=2.0, nb_pts_test_base=3, nb_pts_test_rosace=0)
            possible = aa + bb
        elif inst == PlayingAction.TryToDribble:
            possible = determine_action_possible_locations(Location(r.x, r.y, r.theta), rosace_loc, radius=10.0, nb_pts_test_base=4, nb_pts_test_rosace=5)
        elif inst == PlayingAction.TryToPass:
            possible = determine_action_possible_locations(Location(r.x, r.y, r.theta), rosace_loc, radius=radius_extended)
        elif inst == PlayingAction.TryToDeepPass:
            target_ref = ref.location_action_target_envisagee if (ref and ref.location_action_target_envisagee) else None
            possible = determine_action_possible_locations(Location(r.x, r.y, r.theta), target_ref, radius=radius_extended)

        for loc, is_current in possible:
            if abs(loc.x) > world.half_w or abs(loc.y) > world.half_h:
                continue

            if inst == PlayingAction.TryToShoot:
                best_reward, best_prob, best_goal_y = 0.0, 0.0, 0.0
                for y_goal in [i * 0.25 for i in range(-4, 5)]:
                    rew, prob = evaluate_shoot(world, team, loc, y_goal, respect_3m=True,
                                               robot_start=Location(r.x, r.y, r.theta))
                    if rew > best_reward:
                        best_reward, best_prob, best_goal_y = rew, prob, y_goal
                if best_reward > 0.0:
                    a = ActionQValue(r.robot_id, PlayingAction.MovingWithBall, action_subtype=PlayingAction.TryToShoot)
                    a.action_reward = best_reward
                    a.success_probability = best_prob
                    a.set_envisagee(Location(loc.x, loc.y, math.atan2(best_goal_y - loc.y, goal_x - loc.x)))
                    a.is_current_action_loc = is_current
                    results.append(a)

            elif inst == PlayingAction.TryToPass:
                for mate in team.robots.values():
                    if mate.robot_id == r.robot_id or not mate.active:
                        continue
                    rew, prob = evaluate_pass(world, team, loc, mate)
                    if rew <= 0.0:
                        continue
                    a = ActionQValue(r.robot_id, PlayingAction.MovingWithBall, action_subtype=PlayingAction.TryToPass)
                    a.action_reward = rew
                    a.success_probability = prob
                    ang = math.atan2(mate.y - loc.y, mate.x - loc.x)
                    a.set_envisagee(Location(loc.x, loc.y, ang))
                    a.set_target(Location(mate.x, mate.y, 0.0))
                    a.is_current_action_loc = is_current
                    results.append(a)

            elif inst == PlayingAction.TryToDeepPass:
                best_reward, best_prob, best_goal_y = 0.0, 0.0, 0.0
                for y_goal in [i * 0.25 for i in range(-4, 5)]:
                    rew, prob = evaluate_deep_pass(world, team, Location(r.x, r.y, r.theta), loc, y_goal)
                    if rew > best_reward:
                        best_reward, best_prob, best_goal_y = rew, prob, y_goal
                if best_reward > 0.0:
                    a = ActionQValue(r.robot_id, PlayingAction.MovingWithBall, action_subtype=PlayingAction.TryToDeepPass)
                    a.action_reward = best_reward
                    a.success_probability = best_prob
                    ang = math.atan2(loc.y - r.y, loc.x - r.x)
                    a.set_envisagee(Location(r.x, r.y, ang))
                    a.set_target(Location(loc.x, loc.y, 0.0))
                    a.is_current_action_loc = is_current
                    results.append(a)

            elif inst == PlayingAction.TryToDribble:
                rew, prob = evaluate_dribble(world, team, Location(r.x, r.y, r.theta), loc)
                if rew <= 0.0:
                    continue
                a = ActionQValue(r.robot_id, PlayingAction.MovingWithBall, action_subtype=PlayingAction.TryToDribble)
                a.action_reward = rew
                a.success_probability = prob
                ang = math.atan2(loc.y - r.y, loc.x - r.x)
                a.set_envisagee(Location(loc.x, loc.y, ang))
                a.is_current_action_loc = is_current
                results.append(a)

    return results


# ===== Chọn hành động tốt nhất theo Q (reward * prob) =====
def choose_best_action(actions: List[ActionQValue]) -> Optional[ActionQValue]:
    if not actions:
        return None
    return max(actions, key=lambda a: a.action_reward * max(1e-3, a.success_probability))
