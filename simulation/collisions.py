# simulation/collisions.py
from __future__ import annotations
import math, random
from typing import List, TYPE_CHECKING

# Chỉ import type khi check kiểu, KHÔNG import ở runtime
if TYPE_CHECKING:
    from models.world import World
    from models.robot import Robot

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def clamp_robot_inside_field(world: 'World', r: 'Robot') -> None:
    ex, ey = r.half_extents_xy()
    r.x = _clamp(r.x, -world.half_w + ex, world.half_w - ex)
    r.y = _clamp(r.y, -world.half_h + ey, world.half_h - ey)

def enforce_no_overlap(
    world: 'World',
    *,
    iterations: int = 6,
    clearance: float = 0.01,
    restitution: float = 0.0,
    limit_push_per_iter: float = 0.10,
) -> None:
    robots: List['Robot'] = [r for r in world.all_robots() if r.active]
    n = len(robots)
    if n <= 1:
        for r in robots:
            clamp_robot_inside_field(world, r)
        return

    radii = [r.outer_radius + clearance * 0.5 for r in robots]

    for _ in range(max(1, iterations)):
        order = list(range(n))
        random.shuffle(order)

        for a in range(n):
            i = order[a]
            ri = robots[i]
            xi, yi = ri.x, ri.y

            for j in range(i + 1, n):
                rj = robots[j]
                dx = rj.x - xi
                dy = rj.y - yi
                d2 = dx*dx + dy*dy
                min_d = radii[i] + radii[j]

                if d2 < 1e-12:
                    ang = random.random() * 2.0 * math.pi
                    eps = 1e-3
                    ri.x -= eps*math.cos(ang); ri.y -= eps*math.sin(ang)
                    rj.x += eps*math.cos(ang); rj.y += eps*math.sin(ang)
                    dx = rj.x - ri.x; dy = rj.y - ri.y
                    d2 = dx*dx + dy*dy

                d = math.sqrt(d2)
                if d >= min_d:
                    continue

                nx = dx / d if d > 1e-9 else 1.0
                ny = dy / d if d > 1e-9 else 0.0
                overlap = (min_d - d)

                push = min(0.5 * overlap, limit_push_per_iter)
                ri.x -= nx * push; ri.y -= ny * push
                rj.x += nx * push; rj.y += ny * push

                rvx = rj.vx - ri.vx
                rvy = rj.vy - ri.vy
                vn = rvx*nx + rvy*ny
                if vn < 0.0:
                    j_imp = -(1.0 + restitution) * vn * 0.5
                    ri.vx -= nx * j_imp; ri.vy -= ny * j_imp
                    rj.vx += nx * j_imp; rj.vy += ny * j_imp

        for r in robots:
            clamp_robot_inside_field(world, r)
