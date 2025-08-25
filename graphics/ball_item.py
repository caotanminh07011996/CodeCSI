# graphics/ball_item.py
from __future__ import annotations

import math
from collections import deque
from typing import Deque, Optional

from PyQt5.QtWidgets import QGraphicsItemGroup, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsScene
from PyQt5.QtGui import QBrush, QPen, QPainterPath, QColor
from PyQt5.QtCore import Qt, QPointF

from utils.geom import m2px, len_m2px
from config.constants import BALL_RADIUS, SCALE


class BallItem(QGraphicsItemGroup):
    """
    Hiển thị quả bóng:
      - Thân bóng (ellipse tâm (0,0))
      - Highlight (đốm sáng nhỏ)
      - Mũi vận tốc (tùy chọn)
      - Vệt quỹ đạo (tùy chọn, lưu ở scene coords)

    Dùng:
      ball_item = BallItem()
      scene.addItem(ball_item)
      ...
      ball_item.sync(x_m, y_m, vx, vy)
    """

    def __init__(
        self,
        radius_m: float = BALL_RADIUS,
        color: QColor | Qt.GlobalColor = Qt.yellow,
        *,
        show_velocity: bool = True,
        velocity_scale: float = 0.25,   # 1 m/s → 0.25 m chiều dài mũi tên
        trail_enabled: bool = False,
        trail_capacity: int = 80,       # số điểm tối đa trong vệt
        trail_color: QColor | Qt.GlobalColor = QColor(255, 255, 0, 110),
        trail_width_px: float = 2.0,
    ) -> None:
        super().__init__()

        self._r_m = float(radius_m)
        self._r_px = len_m2px(self._r_m)

        # ---- thân bóng ----
        self._body = QGraphicsEllipseItem(-self._r_px, -self._r_px, 2 * self._r_px, 2 * self._r_px, self)
        self._body.setBrush(QBrush(QColor(color)))
        self._body.setPen(QPen(Qt.black, 1.0))
        self._body.setZValue(10)

        # ---- highlight (đốm sáng) ----
        self._hl = QGraphicsEllipseItem(self)
        self._hl.setPen(QPen(Qt.NoPen))
        self._hl.setBrush(QBrush(QColor(255, 255, 255, 160)))
        self._hl.setZValue(11)
        self._update_highlight_rect()

        # ---- mũi vận tốc ----
        self._show_vel = bool(show_velocity)
        self._vel_scale = float(velocity_scale)
        self._vline: Optional[QGraphicsLineItem] = QGraphicsLineItem(self) if self._show_vel else None
        if self._vline is not None:
            pen = QPen(QColor(20, 20, 20, 180), 2)
            pen.setCosmetic(True)  # không scale theo zoom
            self._vline.setPen(pen)
            self._vline.setZValue(12)

        # ---- vệt quỹ đạo (trail) ----
        self._trail_enabled = bool(trail_enabled)
        self._trail_cap = max(4, int(trail_capacity))
        self._trail_pts: Deque[QPointF] = deque(maxlen=self._trail_cap)  # điểm ở scene-coords (px)
        self._trail: Optional[QGraphicsPathItem] = QGraphicsPathItem() if self._trail_enabled else None
        if self._trail is not None:
            pen = QPen(QColor(trail_color))
            pen.setWidthF(trail_width_px)
            pen.setCosmetic(True)
            self._trail.setPen(pen)
            self._trail.setZValue(5)  # dưới thân bóng

        # Tâm quay/đặt tại (0,0) local
        self.setTransformOriginPoint(0.0, 0.0)

    # ------------------ API công khai ------------------

    def add_to_scene(self, scene: QGraphicsScene) -> None:
        """Tiện ích: thêm trail (nếu có) + group bóng vào scene đúng thứ tự Z."""
        if self._trail is not None:
            scene.addItem(self._trail)
        scene.addItem(self)

    def set_color(self, color: QColor | Qt.GlobalColor) -> None:
        self._body.setBrush(QBrush(QColor(color)))

    def set_radius(self, radius_m: float) -> None:
        """Cập nhật bán kính bóng (m) và hình học liên quan."""
        self._r_m = float(radius_m)
        self._r_px = len_m2px(self._r_m)
        self._body.setRect(-self._r_px, -self._r_px, 2 * self._r_px, 2 * self._r_px)
        self._update_highlight_rect()

    def set_trail_enabled(self, enabled: bool, scene: Optional[QGraphicsScene] = None) -> None:
        if enabled and self._trail is None:
            self._trail_enabled = True
            self._trail = QGraphicsPathItem()
            pen = QPen(QColor(255, 255, 0, 110))
            pen.setWidthF(2.0)
            pen.setCosmetic(True)
            self._trail.setPen(pen)
            self._trail.setZValue(5)
            if scene is not None:
                scene.addItem(self._trail)
        elif not enabled and self._trail is not None:
            # loại khỏi scene; giữ an toàn nếu không có scene
            if self._trail.scene() is not None:
                self._trail.scene().removeItem(self._trail)
            self._trail = None
            self._trail_enabled = False
            self._trail_pts.clear()

    def clear_trail(self) -> None:
        self._trail_pts.clear()
        if self._trail is not None:
            self._trail.setPath(QPainterPath())

    def sync(self, x_m: float, y_m: float, vx: float | None = None, vy: float | None = None) -> None:
        """Đồng bộ vị trí (bắt buộc) và mũi vận tốc/vệt (tuỳ chọn)."""
        # --- vị trí (group đặt theo scene coords) ---
        pos_px = m2px(x_m, y_m)
        self.setPos(pos_px)

        # --- mũi vận tốc ---
        if self._vline is not None and vx is not None and vy is not None:
            # local coords có Oy xuống, nên y_px = -vy
            length_m = math.hypot(vx, vy) * self._vel_scale  # m → scale
            dx_px = len_m2px(length_m) * (vx / (math.hypot(vx, vy) + 1e-12))
            dy_px = len_m2px(length_m) * (-vy / (math.hypot(vx, vy) + 1e-12))
            self._vline.setLine(0.0, 0.0, dx_px, dy_px)
            self._vline.setVisible(length_m > 1e-3)
        elif self._vline is not None:
            self._vline.setVisible(False)

        # --- vệt quỹ đạo ---
        if self._trail is not None:
            self._trail_pts.append(QPointF(pos_px))
            path = QPainterPath()
            # vẽ mượt: bắt đầu từ điểm đầu tiên
            pts = list(self._trail_pts)
            if len(pts) >= 2:
                path.moveTo(pts[0])
                for p in pts[1:]:
                    path.lineTo(p)
            else:
                path.moveTo(pos_px)
            self._trail.setPath(path)

    # ------------------ nội bộ ------------------

    def _update_highlight_rect(self) -> None:
        """Đặt đốm sáng nhỏ lệch lên-trái một chút."""
        r = self._r_px
        a = 0.6 * r
        self._hl.setRect(-0.45 * r, -0.45 * r, a, a)
        self._hl.setVisible(True)
