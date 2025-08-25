from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Tuple, Literal, Optional

BoundaryMode = Literal["clip", "bounce"]

@dataclass
class Ball:
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0

    # Tham số vật lý/cấu hình
    radius: float = 0.11          # ~ đường kính bóng size 5 ~ 0.22 m
    min_speed: float = 0.05       # m/s, dưới ngưỡng thì coi như dừng
    lin_drag_per_s: float = 1.5   # hệ số cản tuyến tính theo giây (tuỳ chỉnh)
    restitution: float = 0.25     # độ đàn hồi khi bật tường (nếu dùng "bounce")

    def pos(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def vel(self) -> Tuple[float, float]:
        return (self.vx, self.vy)

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    @property
    def dir_rad(self) -> float:
        return math.atan2(self.vy, self.vx)

    def set_pos(self, x: float, y: float) -> None:
        self.x = float(x); self.y = float(y)

    def set_vel(self, vx: float, vy: float) -> None:
        self.vx = float(vx); self.vy = float(vy)

    def set_speed_dir(self, speed: float, theta_rad: float) -> None:
        self.vx = float(speed) * math.cos(theta_rad)
        self.vy = float(speed) * math.sin(theta_rad)

    def apply_impulse(self, jx: float, jy: float) -> None:
        """Cộng thêm vận tốc (đơn giản hoá: coi khối lượng = 1)."""
        self.vx += float(jx)
        self.vy += float(jy)

    def kick(self, speed: float, theta_rad: float) -> None:
        """Gán vận tốc theo lực sút."""
        self.set_speed_dir(speed, theta_rad)

    def _time_invariant_damping(self, dt: float) -> float:
        """Hệ số giảm tốc theo dt: exp(-k*dt). k = lin_drag_per_s."""
        k = max(0.0, float(self.lin_drag_per_s))
        return math.exp(-k * dt)

    def update(
        self,
        dt: float,
        field_half_w: Optional[float] = 11.0,  # nửa chiều dài sân (22m → 11)
        field_half_h: Optional[float] = 7.0,   # nửa chiều rộng sân (14m → 7)
        boundary_mode: BoundaryMode = "clip"
    ) -> None:
        if dt <= 0.0:
            return

        # 1) Cập nhật vị trí (Euler) với vận tốc hiện tại
        self.x += self.vx * dt
        self.y += self.vy * dt

        # 2) Giảm tốc không phụ thuộc FPS
        damp = self._time_invariant_damping(dt)
        self.vx *= damp
        self.vy *= damp

        # 3) Kẹp về 0 nếu rất nhỏ
        min_v2 = self.min_speed * self.min_speed
        v2 = self.vx * self.vx + self.vy * self.vy
        if v2 < min_v2:
            self.vx = 0.0
            self.vy = 0.0

        # 4) Xử lý biên sân nếu có thông số sân
        if field_half_w is not None and field_half_h is not None:
            max_x = field_half_w - self.radius
            max_y = field_half_h - self.radius

            if boundary_mode == "clip":
                # Kẹp vị trí trong sân; nếu chạm biên có thể dừng bóng nhẹ
                if self.x > max_x:
                    self.x = max_x; self.vx = 0.0
                elif self.x < -max_x:
                    self.x = -max_x; self.vx = 0.0
                if self.y > max_y:
                    self.y = max_y; self.vy = 0.0
                elif self.y < -max_y:
                    self.y = -max_y; self.vy = 0.0

            elif boundary_mode == "bounce":
                # Bật lại với hệ số đàn hồi
                if self.x > max_x:
                    self.x = max_x
                    self.vx = -self.vx * self.restitution
                elif self.x < -max_x:
                    self.x = -max_x
                    self.vx = -self.vx * self.restitution

                if self.y > max_y:
                    self.y = max_y
                    self.vy = -self.vy * self.restitution
                elif self.y < -max_y:
                    self.y = -max_y
                    self.vy = -self.vy * self.restitution

    def __repr__(self) -> str:
        return f"Ball(x={self.x:.2f}, y={self.y:.2f}, vx={self.vx:.2f}, vy={self.vy:.2f})"
