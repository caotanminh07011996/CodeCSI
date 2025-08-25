# actions/base.py
from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Tuple, Protocol

def wrap_pi(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi

class Status(Enum):
    RUNNING = auto()
    SUCCESS = auto()
    FAILURE = auto()

class HasWorld(Protocol):
    field_w: float
    field_h: float

class HasTeam(Protocol):
    side: str  # "left" hoặc "right"

class HasRobot(Protocol):
    x: float; y: float; theta: float
    vx: float; vy: float; omega: float
    side_len: float
    has_ball: bool
    active: bool
    def command_velocity(self, vx: float, vy: float, omega: float) -> None: ...
    def command_move_towards(self, tx: float, ty: float, speed: float | None = None) -> None: ...
    def command_face_point(self, tx: float, ty: float, kp: float = 3.0, max_rate: float | None = None) -> None: ...

@dataclass(slots=True)
class Action:
    """Base class: mỗi tick gọi `tick(world, team, robot, dt)`."""
    name: str = "Action"
    max_time: Optional[float] = None   # giây; None = không giới hạn
    started: bool = field(default=False, init=False)
    elapsed: float = field(default=0.0, init=False)

    def on_start(self, world: HasWorld, team: HasTeam, robot: HasRobot) -> None:
        pass

    def on_end(self, world: HasWorld, team: HasTeam, robot: HasRobot, status: Status) -> None:
        pass

    def step(self, world: HasWorld, team: HasTeam, robot: HasRobot, dt: float) -> Status:
        """Ghi đè ở lớp con — trả về Status."""
        return Status.SUCCESS

    def tick(self, world: HasWorld, team: HasTeam, robot: HasRobot, dt: float) -> Status:
        if not self.started:
            self.started = True
            self.elapsed = 0.0
            self.on_start(world, team, robot)
        self.elapsed += dt
        if self.max_time is not None and self.elapsed > self.max_time:
            self.on_end(world, team, robot, Status.FAILURE)
            return Status.FAILURE

        st = self.step(world, team, robot, dt)
        if st != Status.RUNNING:
            self.on_end(world, team, robot, st)
        return st
