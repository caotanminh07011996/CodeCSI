# models/robot.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple, List

def _wrap_pi(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

@dataclass
class Robot:
    """
    Robot MSL (thuần logic, không UI) — HÌNH VUÔNG, cạnh side_len (m).
    - Toạ độ: gốc giữa sân, Ox trái→phải, Oy dưới→trên (m), góc rad.
    - Động học: holonomic đơn giản với bám lệnh bậc 1 + giới hạn gia tốc.
    - Hình học vuông dùng cho vẽ/kẹp biên/va chạm (tuỳ simulation sử dụng).
    - Hỗ trợ phát hiện bóng ở phía trước theo 'cone' và neo bóng khi dribble.
    """

    # Định danh
    robot_id: int = 0
    team_id: int = 0

    # Trạng thái (m, rad)
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0

    # Vận tốc hiện tại (m/s, rad/s)
    vx: float = 0.0
    vy: float = 0.0
    omega: float = 0.0

    # Lệnh mục tiêu (do controllers đặt)
    desired_vx: float = 0.0
    desired_vy: float = 0.0
    desired_omega: float = 0.0

    # --- Hình học: robot vuông ---
    side_len: float = 0.45  # cạnh 0.45 m

    # Giới hạn & đáp ứng
    max_speed: float = 2.5
    max_omega: float = 6.0
    max_accel: float = 4.0
    max_alpha: float = 20.0
    tau_v: float = 0.12
    tau_w: float = 0.10

    # Cờ tiện ích
    active: bool = True
    has_ball: bool = False


    # --- DEBUG / UI label ---
    dbg_action: str = ""  # <— tên action đang chọn (để TeamGraphic hiển thị)

    # --------- tiện ích ----------
    @property
    def pose(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.theta)

    @property
    def vel(self) -> Tuple[float, float, float]:
        return (self.vx, self.vy, self.omega)

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    @property
    def theta_deg(self) -> float:
        return math.degrees(self.theta)

    # --- Hình học vuông ---
    @property
    def half_side(self) -> float:
        return 0.5 * self.side_len

    @property
    def outer_radius(self) -> float:
        """Bán kính bao ngoài (nửa đường chéo), hữu ích cho broad-phase."""
        h = self.half_side
        return math.hypot(h, h)

    def corners(self) -> List[Tuple[float, float]]:
        """4 đỉnh theo thứ tự CCW, đã quay theo theta, tịnh tiến tới (x,y)."""
        h = self.half_side
        c, s = math.cos(self.theta), math.sin(self.theta)
        local = [(-h, -h), (h, -h), (h, h), (-h, h)]
        return [(self.x + c*lx - s*ly, self.y + s*lx + c*ly) for lx, ly in local]

    def half_extents_xy(self) -> Tuple[float, float]:
        """
        Nửa bề rộng chiếu lên Ox/Oy của OBB hiện tại.
        Với square: e = h*(|cosθ| + |sinθ|) cho cả Ox và Oy.
        """
        h = self.half_side
        c, s = abs(math.cos(self.theta)), abs(math.sin(self.theta))
        e = h * (c + s)
        return (e, e)

    def aabb(self) -> Tuple[float, float, float, float]:
        xs, ys = zip(*self.corners())
        return (min(xs), max(xs), min(ys), max(ys))

    # --------- set/command ----------
    def set_pose(self, x: float, y: float, theta: float) -> None:
        self.x, self.y, self.theta = float(x), float(y), _wrap_pi(float(theta))

    def set_vel(self, vx: float, vy: float, omega: float) -> None:
        self.vx, self.vy, self.omega = float(vx), float(vy), float(omega)

    def stop(self) -> None:
        self.desired_vx = self.desired_vy = self.desired_omega = 0.0

    def command_velocity(self, vx: float, vy: float, omega: float) -> None:
        sp = math.hypot(vx, vy)
        if sp > 1e-9 and sp > self.max_speed:
            k = self.max_speed / sp
            vx *= k; vy *= k
        omega = _clamp(omega, -self.max_omega, self.max_omega)
        self.desired_vx, self.desired_vy, self.desired_omega = float(vx), float(vy), float(omega)

    def command_move_towards(self, tx: float, ty: float, speed: float | None = None) -> None:
        if speed is None: speed = self.max_speed
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        if d < 1e-6:
            self.command_velocity(0.0, 0.0, self.desired_omega); return
        ux, uy = dx / d, dy / d
        self.command_velocity(ux * speed, uy * speed, self.desired_omega)

    def command_face_point(self, tx: float, ty: float, kp: float = 3.0, max_rate: float | None = None) -> None:
        err = _wrap_pi(math.atan2(ty - self.y, tx - self.x) - self.theta)
        w = kp * err
        self.desired_omega = _clamp(w, - (max_rate or self.max_omega), (max_rate or self.max_omega))

    # --------- cập nhật động học ----------
    def _alpha(self, tau: float, dt: float) -> float:
        if tau <= 0.0: return 1.0
        return 1.0 - math.exp(-dt / tau)

    def update(self, dt: float) -> None:
        if not self.active or dt <= 0.0: return

        # bám lệnh bậc 1
        av = self._alpha(self.tau_v, dt)
        aw = self._alpha(self.tau_w, dt)
        vx_tgt = self.vx + av * (self.desired_vx - self.vx)
        vy_tgt = self.vy + av * (self.desired_vy - self.vy)
        w_tgt  = self.omega + aw * (self.desired_omega - self.omega)

        # kẹp tổng tốc
        sp = math.hypot(vx_tgt, vy_tgt)
        if sp > self.max_speed > 0.0:
            s = self.max_speed / sp
            vx_tgt *= s; vy_tgt *= s
        w_tgt = _clamp(w_tgt, -self.max_omega, self.max_omega)

        # giới hạn gia tốc theo bước dt
        max_dv = self.max_accel * dt
        dvx, dvy = vx_tgt - self.vx, vy_tgt - self.vy
        dv = math.hypot(dvx, dvy)
        if dv > max_dv > 0.0:
            s = max_dv / dv
            dvx *= s; dvy *= s
        self.vx += dvx
        self.vy += dvy
        self.omega += _clamp(w_tgt - self.omega, -self.max_alpha * dt, self.max_alpha * dt)

        # tích phân pose
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.theta = _wrap_pi(self.theta + self.omega * dt)

    # --------- nhận bóng (cone) & dribble ----------
    def ball_relative(self, bx: float, by: float) -> Tuple[float, float]:
        """Trả về (dist, ang_err) với ang_err = góc(bóng) - heading ∈ [-pi, pi]."""
        dx, dy = bx - self.x, by - self.y
        dist = math.hypot(dx, dy)
        ang_err = _wrap_pi(math.atan2(dy, dx) - self.theta)
        return dist, ang_err

    def sees_ball_front(self, bx: float, by: float,
                        max_dist: float = 0.35,
                        half_angle_deg: float = 40.0) -> bool:
        """True nếu bóng ở trước mặt (±half_angle) và trong phạm vi max_dist."""
        dist, ang_err = self.ball_relative(bx, by)
        return (dist <= max_dist) and (abs(ang_err) <= math.radians(half_angle_deg))

    def dribble_anchor(self, ball_radius: float = 0.11, gap: float = 0.015) -> Tuple[float, float, float, float]:
        """
        Tính vị trí & vận tốc 'neo' của bóng khi dính ở mũi robot.
        Trả về (ax, ay, avx, avy).
        """
        h = self.half_side
        front = h + ball_radius + gap        # từ tâm robot → tâm bóng
        c, s = math.cos(self.theta), math.sin(self.theta)

        # Vị trí neo (trước mũi)
        ax = self.x + c * front
        ay = self.y + s * front

        # Vận tốc neo = vận tốc tịnh tiến + thành phần quay (ω × r)
        rx, ry = c * front, s * front        # vector từ tâm → neo (world)
        avx = self.vx - self.omega * ry      # ω×r (2D): (-ω*ry, ω*rx)
        avy = self.vy + self.omega * rx
        return ax, ay, avx, avy

    # --------- debug ----------
    def __repr__(self) -> str:
        return (f"Robot#{self.robot_id}(team={self.team_id}) "
                f"pos=({self.x:.2f},{self.y:.2f},{math.degrees(self.theta):.1f}°) "
                f"vel=({self.vx:.2f},{self.vy:.2f},{self.omega:.2f}) side={self.side_len:.2f}m")
