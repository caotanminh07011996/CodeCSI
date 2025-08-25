# controllers/strategy_planner_full.py
from __future__ import annotations

import math
from typing import Dict, Optional, Tuple, List

from models.world import World
from models.team import Team
from models.robot import Robot

# Action planner (rosace + scoring + executor)
from actions.planning import (
    PlayingAction,
    ActionQValue,
    Location,
    build_move_with_ball_actions,
    choose_best_action,
    can_execute_at,
    exec_shoot,
    exec_pass,
)

# Primitive actions for non-holder roles
#from actions.ball import SeekBall
from actions.positioning import (
    PositioningPlayingBall,
    PositioningAssist,
    PositioningDefense,
    GoalKeeping,
    SeekBall,
)


class StrategyPlannerFull:
    """
    Chiến thuật đầy đủ cho 1 team:
      - Nếu đội mình giữ bóng: holder dùng planner (Shoot/Pass/DeepPass/Dribble),
        còn lại: PositioningPlayingBall / Assist / Defense / GoalKeeping.
      - Nếu không giữ bóng: 1 robot đuổi bóng (SeekBall), còn lại phòng ngự; 1 robot làm GK.

    Gọi decide(world) mỗi tick trước world.update(dt).
    """

    def __init__(
        self,
        team_side: str,                # "left" | "right"
        primary_attacker_id: int = 1,  # mặc định #1 là holder ưu tiên khi có bóng
        allowed_per_robot: Optional[Dict[int, set[int]]] = None,  # PlayingAction.* instant
    ):
        self.team_side = team_side
        self.primary_attacker_id = primary_attacker_id
        self.allowed_per_robot = allowed_per_robot or {}

        # "Sticky" để rosace bám theo action đã chọn (giống C#)
        # key = rid*10000 + PlayingAction.MovingWithBall*100 + subAction
        self.imagined_optimal: Dict[int, ActionQValue] = {}

        # Các instance action dùng lại (không cấp phát mỗi frame)
        self._seek_cache: Dict[int, SeekBall] = {}
        self._pos_play_cache: Dict[int, PositioningPlayingBall] = {}
        self._assist_cache: Dict[int, PositioningAssist] = {}
        self._def_cache: Dict[int, PositioningDefense] = {}
        self._gk_cache: Dict[int, GoalKeeping] = {}

    # ------------------------ public ------------------------

    def decide(self, world: World) -> None:
        team = world.team_left if self.team_side == "left" else world.team_right
        if len(team.robots) == 0:
            return

        # 1) chọn GK (robot gần khung thành nhà nhất)
        gk_id = self._select_goalkeeper(world, team)

        # 2) xác định holder (đội mình có giữ bóng không?)
        holder_id = self._find_holder_id(team)
        opp_holder = self._find_holder_id(world.team_right if team is world.team_left else world.team_left)

        if holder_id is not None:
            # --- ATTACK MODE: mình đang giữ bóng ---
            self._attack_mode(world, team, gk_id, holder_id)
        else:
            # --- DEFENSE MODE: không giữ bóng (đối thủ có hoặc bóng tự do) ---
            self._defense_mode(world, team, gk_id, opp_holder)

    # ------------------------ modes ------------------------

    def _attack_mode(self, world: World, team: Team, gk_id: int, holder_id: int) -> None:
        # 1) Holder → planner chọn instant action & thi hành thật
        holder = team.get(holder_id)
        if holder and holder.active:
            self._act_with_ball(world, team, holder)

        # 2) Vai trò còn lại
        others: List[int] = [rid for rid in team.robots.keys() if rid != holder_id]
        # đảm bảo GK luôn GK
        if gk_id in others:
            self._goalkeep(world, team, gk_id)
            others.remove(gk_id)

        # Ưu tiên 1 người PositioningPlayingBall (làm tuyến nhận),
        # 1-2 người Assist (mở tam giác), phần còn lại Defense
        if others:
            rid_pb = others.pop(0)
            self._pos_playing_ball(world, team, rid_pb)
        for _ in range(min(2, len(others))):
            rid_as = others.pop(0)
            self._assist(world, team, rid_as)
        for rid_df in others:
            self._defend(world, team, rid_df)

    def _defense_mode(self, world: World, team: Team, gk_id: int, opp_holder_id: Optional[int]) -> None:
        # 1) GK luôn GK
        self._goalkeep(world, team, gk_id)

        # 2) Chọn chaser (gần bóng nhất, tránh GK)
        chaser_id = self._nearest_to_ball(world, team, exclude={gk_id})
        if chaser_id is not None:
            self._seek_ball(world, team, chaser_id)

        # 3) Phần còn lại đứng phòng ngự (độ sâu tăng nếu đối thủ giữ bóng)
        for rid, r in team.robots.items():
            if not r.active or rid in (gk_id, chaser_id):
                continue
            depth = 2.5 if opp_holder_id is not None else 2.0
            self._defend(world, team, rid, depth=depth)

    # ------------------------ holder planner ------------------------

    def _act_with_ball(self, world: World, team: Team, r: Robot) -> None:
        actions = build_move_with_ball_actions(
            world, team, r.robot_id,
            team_possible_actions=self.allowed_per_robot,
            imagined_optimal_long_actions=self.imagined_optimal,
        )
        best = choose_best_action(actions)
        if not best:
            # fallback nhỏ: dribble thẳng về phía cầu môn đối phương
            goal_x = world.half_w if team.side == "left" else -world.half_w
            r.dbg_action = "FallbackDribble"               # <-- thêm
            r.command_face_point(goal_x, 0.0)
            r.command_move_towards(goal_x, 0.0, speed=1.5)
            return

        # lưu sticky
        key = r.robot_id * 10000 + PlayingAction.MovingWithBall * 100 + (best.action_subtype or 0)
        self.imagined_optimal[key] = best

        env = best.location_action_envisagee
        tgt = best.location_action_target_envisagee

        # đặt tên action để UI hiển thị
        try:
            r.dbg_action = PlayingAction(best.action_subtype or best.imagined_robot_action).name
        except Exception:
            r.dbg_action = "MovingWithBall"

        if best.action_subtype == PlayingAction.TryToShoot:
            goal_x = world.half_w if team.side == "left" else -world.half_w
            r.command_move_towards(env.x, env.y, speed=1.6)
            r.command_face_point(goal_x, 0.0)
            if r.has_ball and can_execute_at(r, env):
                exec_shoot(world, team, r)

        elif best.action_subtype == PlayingAction.TryToPass and tgt is not None:
            r.command_move_towards(env.x, env.y, speed=1.4)
            r.command_face_point(tgt.x, tgt.y)
            if r.has_ball and can_execute_at(r, env):
                exec_pass(world, team, r, (tgt.x, tgt.y))

        elif best.action_subtype == PlayingAction.TryToDeepPass and tgt is not None:
            r.command_move_towards(env.x, env.y, speed=1.4)
            r.command_face_point(tgt.x, tgt.y)
            if r.has_ball and can_execute_at(r, env):
                exec_pass(world, team, r, (tgt.x, tgt.y))

        elif best.action_subtype == PlayingAction.TryToDribble:
            r.command_face_point(env.x, env.y)
            r.command_move_towards(env.x, env.y, speed=1.6)

        else:
            goal_x = world.half_w if team.side == "left" else -world.half_w
            r.dbg_action = "FallbackMove"                  # <-- thêm
            r.command_face_point(goal_x, 0.0)
            r.command_move_towards(goal_x, 0.0, speed=1.2)


    # ------------------------ role helpers ------------------------

    def _seek_ball(self, world: World, team: Team, rid: int) -> None:
        r = team.get(rid)
        if not r or not r.active:
            return
        act = self._seek_cache.get(rid)
        if act is None:
            act = SeekBall(approach_speed=1.8, capture_dist=0.35)
            self._seek_cache[rid] = act
        r.dbg_action = "SeekBall"                 # <-- thêm
        act.tick(world, team, r, dt=0.0)

    def _pos_playing_ball(self, world: World, team: Team, rid: int) -> None:
        r = team.get(rid)
        if not r or not r.active:
            return
        act = self._pos_play_cache.get(rid)
        if act is None:
            act = PositioningPlayingBall(offset_back=1.2, offset_side=0.8)
            self._pos_play_cache[rid] = act
        r.dbg_action = "PositioningPlayingBall"   # <-- thêm
        act.tick(world, team, r, dt=0.0)

    def _assist(self, world: World, team: Team, rid: int) -> None:
        r = team.get(rid)
        if not r or not r.active:
            return
        act = self._assist_cache.get(rid)
        if act is None:
            act = PositioningAssist(radial=2.5, angle_deg=35)
            self._assist_cache[rid] = act
        r.dbg_action = "PositioningAssist"        # <-- thêm
        act.tick(world, team, r, dt=0.0)

    def _defend(self, world: World, team: Team, rid: int, depth: float = 2.5) -> None:
        r = team.get(rid)
        if not r or not r.active:
            return
        act = self._def_cache.get(rid)
        if act is None:
            act = PositioningDefense(depth=depth)
            self._def_cache[rid] = act
        else:
            act.depth = depth
        r.dbg_action = "PositioningDefense"       # <-- thêm
        act.tick(world, team, r, dt=0.0)

    def _goalkeep(self, world: World, team: Team, rid: int) -> None:
        r = team.get(rid)
        if not r or not r.active:
            return
        act = self._gk_cache.get(rid)
        if act is None:
            act = GoalKeeping(line_depth=0.4)
            self._gk_cache[rid] = act
        r.dbg_action = "GoalKeeping"              # <-- thêm
        act.tick(world, team, r, dt=0.0)


    # ------------------------ utilities ------------------------

    def _find_holder_id(self, team: Team) -> Optional[int]:
        for rid, r in team.robots.items():
            if r.active and r.has_ball:
                return rid
        return None

    def _nearest_to_ball(self, world: World, team: Team, exclude: set[int] = set()) -> Optional[int]:
        bx, by = world.ball.x, world.ball.y
        best_id, best_d2 = None, 1e18
        for rid, r in team.robots.items():
            if not r.active or rid in exclude:
                continue
            d2 = (r.x - bx) ** 2 + (r.y - by) ** 2
            if d2 < best_d2:
                best_d2, best_id = d2, rid
        return best_id

    def _select_goalkeeper(self, world: World, team: Team) -> int:
        """Chọn robot gần khung thành nhà nhất làm GK."""
        own_goal_x = -world.half_w if team.side == "left" else world.half_w
        best_id, best = list(team.robots.keys())[0], 1e18
        for rid, r in team.robots.items():
            d = abs(r.x - own_goal_x)
            if d < best:
                best, best_id = d, rid
        return best_id
