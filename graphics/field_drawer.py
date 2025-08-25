# graphics/field_drawer.py

'''
from __future__ import annotations

import math
from typing import Optional

from PyQt5.QtWidgets import QGraphicsScene, QGraphicsItemGroup
from PyQt5.QtGui import QPen, QBrush, QColor
from PyQt5.QtCore import Qt, QRectF, QPointF

from config.constants import FIELD_W, FIELD_H, SCALE, MARGIN
from utils.geom import m2px, len_m2px


def rectf_from_points(a, b) -> QRectF:
    # a, b có thể là tuple hoặc QPointF
        if not isinstance(a, QPointF):
            a = QPointF(a[0], a[1])
        if not isinstance(b, QPointF):
            b = QPointF(b[0], b[1])
        return QRectF(a, b)


class FieldDrawer:
    """
    Vẽ sân bóng 22×14 m theo hệ toạ độ gốc giữa sân (m), Oy hướng lên.
    - KHÔNG gọi scene.clear()
    - Tạo một QGraphicsItemGroup để gom các nét vẽ của sân
    - Căn tâm sân trùng (0,0) trong hệ mét

    Mặc định:
      - Tô nền xanh cỏ (tuỳ chọn)
      - Vẽ viền sân, vạch giữa, vòng tròn tâm, chấm giữa sân, vòng cấm địa đơn giản
      - Vẽ khung thành (ngoài sân)
    """

    def __init__(
        self,
        *,
        line_color: QColor = Qt.white,
        turf_color: Optional[QColor] = QColor("#186a3b"),  # None để bỏ tô nền
        line_width_px: int = 2,
        center_circle_r_m: float = 1.0,
        center_dot_r_m: float = 0.05,
        penalty_depth_m: float = 3.0,   # chiều sâu vùng cấm địa tính từ vạch vôi
        penalty_width_m: float = 8.0,   # bề rộng vùng cấm địa (đối xứng qua Oy)
        goal_width_m: float = 2.0,      # miệng khung thành (±1.0 m theo Oy)
        goal_depth_m: float = 0.6,      # độ sâu khung thành ra ngoài sân
        corner_arc_r_m: float = 0.5,    # bán kính cung phạt góc
        draw_corner_arcs: bool = True,
        draw_goals: bool = True,
        draw_penalty_boxes: bool = True,
        draw_center: bool = True,
    ):
        self.line_pen = QPen(line_color, line_width_px)
        self.boundary_pen = QPen(line_color, max(2, line_width_px))
        self.turf_brush = QBrush(turf_color) if turf_color is not None else None

        self.center_circle_r_m = center_circle_r_m
        self.center_dot_r_m = center_dot_r_m
        self.penalty_depth_m = penalty_depth_m
        self.penalty_width_m = penalty_width_m
        self.goal_width_m = goal_width_m
        self.goal_depth_m = goal_depth_m
        self.corner_arc_r_m = corner_arc_r_m

        self.draw_corner_arcs = draw_corner_arcs
        self.draw_goals = draw_goals
        self.draw_penalty_boxes = draw_penalty_boxes
        self.draw_center = draw_center

        self.group: Optional[QGraphicsItemGroup] = None  # group chứa các nét vẽ sân

    # ------------------------ tiện ích px ------------------------

    @staticmethod
    def _scene_rect_px() -> QRectF:
        """Hộp bao toàn scene (px) để setSceneRect (bao gồm lề)."""
        w_px = FIELD_W * SCALE + 2 * MARGIN
        h_px = FIELD_H * SCALE + 2 * MARGIN
        return QRectF(0.0, 0.0, w_px, h_px)

    # ------------------------ API chính ------------------------

    def draw(self, scene: QGraphicsScene) -> QGraphicsItemGroup:
        """
        Vẽ sân lên scene và trả về group chứa các nét vẽ của sân.
        Gọi lại nhiều lần sẽ thay thế group cũ (nếu có) bằng group mới.
        """
        # 1) Thiết lập vùng scene (không xoá item khác)
        scene.setSceneRect(self._scene_rect_px())

        # 2) Nếu đã có group cũ, tháo nó ra (không ảnh hưởng robot/ball)
        if self.group is not None:
            scene.removeItem(self.group)
            self.group = None

        group = QGraphicsItemGroup()
        scene.addItem(group)
        self.group = group

        # 3) Tô nền cỏ (tuỳ chọn)
        if self.turf_brush is not None:
            tl = m2px(-FIELD_W / 2, FIELD_H / 2)
            br = m2px(FIELD_W / 2, -FIELD_H / 2)
            #rect = rectf_from_points(tl, br)
            #rect = rect.normalized()
            rect = rectf_from_points(tl, br).normalized()
            bg = scene.addRect(rect, QPen(Qt.NoPen), self.turf_brush)
            bg.setZValue(-100)  # nằm dưới cùng
            group.addToGroup(bg)

        # 4) Viền sân (đường biên)
        self._add_field_boundary(scene, group)

        # 5) Vạch giữa sân + vòng tròn tâm + chấm giữa
        if self.draw_center:
            self._add_center_lines(scene, group)

        # 6) Vòng cấm địa (hình chữ nhật đơn giản)
        if self.draw_penalty_boxes:
            self._add_penalty_boxes(scene, group)

        # 7) Cung phạt góc
        if self.draw_corner_arcs and self.corner_arc_r_m > 0:
            self._add_corner_arcs(scene, group)

        # 8) Khung thành (ngoài sân)
        if self.draw_goals and self.goal_depth_m > 0 and self.goal_width_m > 0:
            self._add_goals(scene, group)

        return group

    # ------------------------ các phần vẽ ------------------------

    def _add_field_boundary(self, scene: QGraphicsScene, group: QGraphicsItemGroup) -> None:
        tl = m2px(-FIELD_W / 2, FIELD_H / 2)
        br = m2px(FIELD_W / 2, -FIELD_H / 2)
        rect = rectf_from_points(tl, br).normalized()
        it = scene.addRect(rect, self.boundary_pen, QBrush(Qt.NoBrush))
        group.addToGroup(it)

    def _add_center_lines(self, scene: QGraphicsScene, group: QGraphicsItemGroup) -> None:
        # vạch giữa
        p1 = m2px(0.0, FIELD_H / 2)
        p2 = m2px(0.0, -FIELD_H / 2)
        ln = scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), self.line_pen)
        group.addToGroup(ln)

        # vòng tròn tâm
        c = m2px(0.0, 0.0)
        r = len_m2px(self.center_circle_r_m)
        circ = scene.addEllipse(c.x() - r, c.y() - r, 2 * r, 2 * r, self.line_pen)
        group.addToGroup(circ)

        # chấm giữa sân
        dot_r_px = len_m2px(self.center_dot_r_m)
        dot = scene.addEllipse(c.x() - dot_r_px, c.y() - dot_r_px,
                               2 * dot_r_px, 2 * dot_r_px,
                               self.line_pen, QBrush(self.line_pen.color()))
        group.addToGroup(dot)

    def _add_penalty_boxes(self, scene: QGraphicsScene, group: QGraphicsItemGroup) -> None:
        """Hình chữ nhật vùng cấm địa đơn giản (tuỳ chỉnh kích thước)."""
        half_w = FIELD_W / 2
        half_h = FIELD_H / 2
        hw_box = self.penalty_width_m / 2
        d = self.penalty_depth_m

        # Trái (hướng x âm): từ -half_w tới -half_w + d, y trong [-hw_box, +hw_box]
        tl_l = m2px(-half_w + d, hw_box)
        br_l = m2px(-half_w, -hw_box)
        rect_l = rectf_from_points(tl_l, br_l).normalized()
        itl = scene.addRect(rect_l, self.line_pen, QBrush(Qt.NoBrush))
        group.addToGroup(itl)

        # Phải (hướng x dương): từ half_w - d tới half_w
        tl_r = m2px(half_w - d, hw_box)
        br_r = m2px(half_w, -hw_box)
        rect_r = rectf_from_points(tl_r, br_r).normalized()
        itr = scene.addRect(rect_r, self.line_pen, QBrush(Qt.NoBrush))
        group.addToGroup(itr)
    """
    def _add_corner_arcs(self, scene: QGraphicsScene, group: QGraphicsItemGroup) -> None:
        r_px = len_m2px(self.corner_arc_r_m)

        # Các góc (m): (±FIELD_W/2, ±FIELD_H/2)
        corners = [
            (-FIELD_W / 2,  FIELD_H / 2, 180, 90),  # top-left: bắt đầu 180°, quét 90°
            ( FIELD_W / 2,  FIELD_H / 2, 270, 90),  # top-right
            ( FIELD_W / 2, -FIELD_H / 2,   0, 90),  # bottom-right
            (-FIELD_W / 2, -FIELD_H / 2,  90, 90),  # bottom-left
        ]
        for (xm, ym, start_deg, span_deg) in corners:
            # Hộp bao vòng cung nằm trong sân, tiếp xúc biên
            cx = max(-FIELD_W / 2, min(FIELD_W / 2, xm))
            cy = max(-FIELD_H / 2, min(FIELD_H / 2, ym))
            center = m2px(cx, cy)
            rect = QRectF(center.x() - r_px, center.y() - r_px, 2 * r_px, 2 * r_px)
            arc = scene.addArc(rect, start_deg * 16, span_deg * 16, self.line_pen)
            group.addToGroup(arc)

    """
    def _add_corner_arcs(self, scene: QGraphicsScene, group: QGraphicsItemGroup) -> None:
        r_px = len_m2px(self.corner_arc_r_m)
        # (xm, ym, startDeg, spanDeg)
        corners = [
            (-FIELD_W/2,  FIELD_H/2, 180, 90),  # top-left
            ( FIELD_W/2,  FIELD_H/2, 270, 90),  # top-right
            ( FIELD_W/2, -FIELD_H/2,   0, 90),  # bottom-right
            (-FIELD_W/2, -FIELD_H/2,  90, 90),  # bottom-left
        ]
        for (xm, ym, start_deg, span_deg) in corners:
            cx = max(-FIELD_W / 2, min(FIELD_W / 2, xm))
            cy = max(-FIELD_H / 2, min(FIELD_H / 2, ym))
            center = m2px(cx, cy)  # QPointF
            rect = QRectF(center.x() - r_px, center.y() - r_px, 2 * r_px, 2 * r_px)
            item = scene.addEllipse(rect, self.line_pen, QBrush(Qt.NoBrush))
            item.setStartAngle(int(start_deg * 16))
            item.setSpanAngle(int(span_deg * 16))
            group.addToGroup(item)


    def _add_goals(self, scene: QGraphicsScene, group: QGraphicsItemGroup) -> None:
        """Vẽ khung thành *ngoài* sân, đối xứng hai bên."""
        half_w = FIELD_W / 2
        w = self.goal_width_m / 2
        d = self.goal_depth_m

        # Trái: khung thành nằm ở x = -half_w - d .. -half_w, y ∈ [-w, +w]
        tl_l = m2px(-half_w,  w)
        br_l = m2px(-half_w - d, -w)
        rect_l = rectf_from_points(tl_l, br_l).normalized()
        itl = scene.addRect(rect_l, self.line_pen, QBrush(Qt.NoBrush))
        group.addToGroup(itl)

        # Phải
        tl_r = m2px(half_w,  w)
        br_r = m2px(half_w + d, -w)
        rect_r = rectf_from_points(tl_r, br_r).normalized()
        itr = scene.addRect(rect_r, self.line_pen, QBrush(Qt.NoBrush))
        group.addToGroup(itr)
    

    


    # ------------------------ tiện ích khác ------------------------

    @staticmethod
    def is_inside_field(x_m: float, y_m: float) -> bool:
        """Điểm (m) nằm trong biên sân (kể cả vạch) — dùng nhanh cho logic."""
        return (-FIELD_W / 2) <= x_m <= (FIELD_W / 2) and (-FIELD_H / 2) <= y_m <= (FIELD_H / 2)
'''


# graphics/field_drawer.py
from __future__ import annotations
import math
from typing import Optional

from PyQt5.QtWidgets import (
    QGraphicsRectItem, QGraphicsLineItem,
    QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsScene
)
from PyQt5.QtGui import QBrush, QPen, QColor, QPainterPath
from PyQt5.QtCore import Qt, QRectF, QPointF

try:
    from config.constants import SCALE as CFG_SCALE
except Exception:
    CFG_SCALE = 60  # fallback

class FieldDrawer:
    """
    Vẽ sân với hệ toạ độ pixel gốc ở (0,0) góc trái trên (giống file mẫu).
    - Chiều dài thực 22m, rộng 14m. Margin = 1m mỗi cạnh.
    - Gọi draw(scene) sẽ scene.clear() rồi vẽ lại toàn bộ sân.
    """

    def __init__(self, scale: Optional[float] = None):
        self.SCALE = float(CFG_SCALE if scale is None else scale)
        self.init_parameters()

    # ------- tham số dựng hình (theo file mẫu) -------
    def init_parameters(self):
        s = self.SCALE
        self.FIELD_WIDTH  = 22.0 * s
        self.FIELD_HEIGHT = 14.0 * s
        self.MARGIN = 1.0 * s

        self.WIDTH  = self.FIELD_WIDTH + 2 * self.MARGIN
        self.HEIGHT = self.FIELD_HEIGHT + 2 * self.MARGIN

        self.C = 6.9 * s     # chiều cao penalty lớn
        self.D = 3.9 * s     # chiều cao small box
        self.E = 2.25 * s    # chiều sâu penalty lớn (theo trục x)
        self.F = 0.75 * s    # chiều sâu small box
        self.G = 0.75 * s    # bán kính cung phạt góc
        self.H = 2.0 * s / 2 # bán kính vòng tròn giữa sân (r=1.0m)
        self.I = 3.6 * s     # lệch tâm chấm 11m (theo mẫu)
        self.J = 0.15 * s / 2  # bán kính chấm giữa & chấm phạt
        self.K = int(0.125 * s)  # bề rộng vạch vôi (px)

        self.GOAL_DEPTH  = 0.7 * s
        self.GOAL_HEIGHT = 2.5 * s

    # ------- API chính -------
    def draw(self, scene: QGraphicsScene):
        scene.clear()
        self.draw_background(scene)
        self.draw_border(scene)
        self.draw_center_line(scene)
        self.draw_center_circle(scene)
        self.draw_penalty_area(scene, self.MARGIN, True)                      # trái
        self.draw_penalty_area(scene, self.WIDTH - self.MARGIN, False)        # phải
        self.draw_corners(scene)
        self.draw_goal(scene, self.MARGIN - self.GOAL_DEPTH, True)            # trái
        self.draw_goal(scene, self.WIDTH - self.MARGIN, False)                # phải

    # ------- các phần vẽ -------
    def draw_background(self, scene: QGraphicsScene):
        field = QGraphicsRectItem(0, 0, self.WIDTH, self.HEIGHT)
        field.setBrush(QBrush(QColor(0, 153, 0)))
        field.setPen(QPen(Qt.NoPen))
        scene.addItem(field)

    def draw_border(self, scene: QGraphicsScene):
        border = QGraphicsRectItem(self.MARGIN, self.MARGIN,
                                   self.FIELD_WIDTH, self.FIELD_HEIGHT)
        border.setPen(QPen(Qt.white, self.K))
        border.setBrush(QBrush(Qt.NoBrush))
        scene.addItem(border)

    def draw_center_line(self, scene: QGraphicsScene):
        center_line = QGraphicsLineItem(self.WIDTH / 2, self.MARGIN,
                                        self.WIDTH / 2, self.HEIGHT - self.MARGIN)
        center_line.setPen(QPen(Qt.white, self.K))
        scene.addItem(center_line)

    def draw_center_circle(self, scene: QGraphicsScene):
        center = QPointF(self.WIDTH / 2, self.HEIGHT / 2)
        circle = QGraphicsEllipseItem(center.x() - self.H, center.y() - self.H,
                                      2 * self.H, 2 * self.H)
        circle.setPen(QPen(Qt.white, self.K))
        circle.setBrush(QBrush(Qt.NoBrush))
        scene.addItem(circle)

        dot = QGraphicsEllipseItem(center.x() - self.J, center.y() - self.J,
                                   2 * self.J, 2 * self.J)
        dot.setBrush(QBrush(Qt.white))
        dot.setPen(QPen(Qt.NoPen))
        scene.addItem(dot)

    def draw_penalty_area(self, scene: QGraphicsScene, x_pos: float, is_left: bool):
        # Vùng cấm lớn
        rect = QGraphicsRectItem(x_pos,
                                 self.HEIGHT / 2 - self.C / 2,
                                 ( self.E if is_left else -self.E),
                                 self.C)
        rect.setPen(QPen(Qt.white, self.K))
        rect.setBrush(QBrush(Qt.NoBrush))
        scene.addItem(rect)

        # Chấm phạt
        dot_x = x_pos + ( self.I if is_left else -self.I )
        penalty_dot = QGraphicsEllipseItem(dot_x - self.J,
                                           self.HEIGHT / 2 - self.J,
                                           2 * self.J, 2 * self.J)
        penalty_dot.setBrush(QBrush(Qt.white))
        penalty_dot.setPen(QPen(Qt.NoPen))
        scene.addItem(penalty_dot)

        # Small box
        small_rect = QGraphicsRectItem(x_pos,
                                       self.HEIGHT / 2 - self.D / 2,
                                       ( self.F if is_left else -self.F),
                                       self.D)
        small_rect.setPen(QPen(Qt.white, self.K))
        small_rect.setBrush(QBrush(Qt.NoBrush))
        scene.addItem(small_rect)

    def draw_corners(self, scene: QGraphicsScene):
        # (x, y, góc bắt đầu, góc kết thúc) theo rad
        positions = [
            (self.MARGIN,                   self.MARGIN,                    3*math.pi/2, 2*math.pi),     # TL
            (self.MARGIN,                   self.HEIGHT - self.MARGIN,      0,            math.pi/2),     # BL
            (self.WIDTH - self.MARGIN,      self.MARGIN,                    math.pi,      3*math.pi/2),   # TR
            (self.WIDTH - self.MARGIN,      self.HEIGHT - self.MARGIN,      math.pi/2,    math.pi),       # BR
        ]
        for x, y, start_angle, end_angle in positions:
            path = QPainterPath()
            path.moveTo(x, y)
            # arcTo(x, y, w, h, startAngleDeg, sweepLengthDeg)
            path.arcTo(x - self.G, y - self.G, 2 * self.G, 2 * self.G,
                       start_angle * 180 / math.pi,
                       (end_angle - start_angle) * 180 / math.pi)
            corner = QGraphicsPathItem(path)
            corner.setPen(QPen(Qt.white, self.K))
            corner.setBrush(QBrush(Qt.NoBrush))
            scene.addItem(corner)

    def draw_goal(self, scene: QGraphicsScene, x_pos: float, is_left: bool):
        # Khung thành (hình chữ nhật)
        goal = QGraphicsRectItem(x_pos,
                                 self.HEIGHT / 2 - self.GOAL_HEIGHT / 2,
                                 self.GOAL_DEPTH, self.GOAL_HEIGHT)
        goal.setPen(QPen(Qt.white, self.K))
        goal.setBrush(QBrush(Qt.NoBrush))
        scene.addItem(goal)

        # Lưới mờ
        net_x = x_pos if is_left else (x_pos + self.GOAL_DEPTH)
        net_w = (-self.GOAL_DEPTH * 0.3) if is_left else (self.GOAL_DEPTH * 0.3)
        net = QGraphicsRectItem(net_x,
                                self.HEIGHT / 2 - self.GOAL_HEIGHT / 2,
                                net_w, self.GOAL_HEIGHT)
        net.setBrush(QBrush(QColor(255, 255, 255, 100)))
        net.setPen(QPen(Qt.NoPen))
        scene.addItem(net)

    # ------- tiện ích phụ (giữ cho tương thích nếu nơi khác có dùng) -------
    def get_dimensions(self):
        """Trả về (width_px, height_px) của vùng vẽ."""
        return self.WIDTH, self.HEIGHT

    def is_inside_field(self, x: float, y: float) -> bool:
        """Kiểm tra toạ độ *mét* có nằm trong sân (±11, ±7) không."""
        return -11.0 <= x <= 11.0 and -7.0 <= y <= 7.0

