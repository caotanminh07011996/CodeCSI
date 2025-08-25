# graphics/team_graphic.py

'''
from __future__ import annotations

import math
from typing import Dict

from PyQt5.QtWidgets import QGraphicsItemGroup, QGraphicsRectItem, QGraphicsPathItem, QGraphicsTextItem, QGraphicsEllipseItem, QGraphicsScene
from PyQt5.QtGui import QBrush, QPen, QPainterPath, QFont, QColor
from PyQt5.QtCore import Qt

from utils.geom import m2px, len_m2px
from models.team import Team


class RobotItem(QGraphicsItemGroup):
    """Một robot vẽ dạng hình vuông + mũi hướng + nhãn ID + halo khi giữ bóng."""
    def __init__(self, side_m: float, color: QColor, robot_id: int):
        super().__init__()

        s_px = len_m2px(side_m)

        # Thân vuông, tâm tại (0,0)
        body = QGraphicsRectItem(-s_px / 2, -s_px / 2, s_px, s_px, self)
        body.setBrush(QBrush(color))
        body.setPen(QPen(Qt.black, 1.5))
        body.setZValue(1)

        # Mũi hướng (tam giác, trỏ về +x local)
        tri = QGraphicsPathItem(self)
        tri.setZValue(2)
        path = QPainterPath()
        path.moveTo(+0.45 * s_px, 0.0)
        path.lineTo(-0.15 * s_px, -0.22 * s_px)
        path.lineTo(-0.15 * s_px, +0.22 * s_px)
        path.closeSubpath()
        tri.setPath(path)
        tri.setBrush(QBrush(Qt.white))
        tri.setPen(QPen(Qt.NoPen))

        # Nhãn ID
        label = QGraphicsTextItem(str(robot_id), self)
        label.setFont(QFont("Arial", 9, weight=QFont.Bold))
        label.setDefaultTextColor(Qt.black)
        label.setPos(-0.5 * s_px, -0.6 * s_px)  # đặt góc trên-trái
        label.setZValue(3)

        # Halo khi has_ball
        halo_r = 0.6 * s_px
        halo = QGraphicsEllipseItem(-halo_r, -halo_r, 2 * halo_r, 2 * halo_r, self)
        halo.setPen(QPen(QColor("yellow"), 2))
        halo.setBrush(QBrush(Qt.NoBrush))
        halo.setZValue(0)
        halo.setVisible(False)

        # Lưu refs
        self._s_px = s_px
        self._body = body
        self._tri = tri
        self._label = label
        self._halo = halo

        # Tâm quay tại tâm hình vuông
        self.setTransformOriginPoint(0.0, 0.0)

    def sync(self, x_m: float, y_m: float, theta_rad: float, active: bool, has_ball: bool):
        self.setPos(m2px(x_m, y_m))
        self.setRotation(-math.degrees(theta_rad))  # Qt dùng degree, CW
        self.setOpacity(1.0 if active else 0.3)
        self._halo.setVisible(has_ball)


class TeamGraphic:
    """
    Quản lý các RobotItem của một Team.
    - Không clear toàn bộ mỗi frame; chỉ thêm/xóa/sync theo robot_id.
    - Màu team truyền ở constructor.
    """
    def __init__(self, team: Team, scene: QGraphicsScene, color: QColor | Qt.GlobalColor):
        self.team = team
        self.scene = scene
        self.color = QColor(color)
        self.items: Dict[int, RobotItem] = {}  # robot_id -> RobotItem

    # Tạo item mới nếu robot mới xuất hiện; xóa item nếu robot biến mất
    def ensure_items(self):
        current_ids = {r.robot_id for r in self.team.robots_list()}

        # remove những item không còn trong đội
        for rid in list(self.items.keys()):
            if rid not in current_ids:
                self.scene.removeItem(self.items[rid])
                del self.items[rid]

        # thêm item cho robot mới
        for r in self.team.robots_list():
            if r.robot_id not in self.items:
                item = RobotItem(side_m=r.side_len, color=self.color, robot_id=r.robot_id)
                self.items[r.robot_id] = item
                self.scene.addItem(item)

    def sync(self):
        self.ensure_items()
        for r in self.team.robots_list():
            self.items[r.robot_id].sync(r.x, r.y, r.theta, r.active, r.has_ball)

    def clear(self):
        for item in self.items.values():
            self.scene.removeItem(item)
        self.items.clear()

'''

# graphics/team_graphic.py
from __future__ import annotations

import math
from typing import Dict

from PyQt5.QtWidgets import (
    QGraphicsItemGroup, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsTextItem, QGraphicsEllipseItem, QGraphicsScene,
    QGraphicsSimpleTextItem
)
from PyQt5.QtGui import QBrush, QPen, QPainterPath, QFont, QColor
from PyQt5.QtCore import Qt

from utils.geom import m2px, len_m2px
from models.team import Team


class RobotItem(QGraphicsItemGroup):
    """Một robot vẽ dạng hình vuông + mũi hướng + nhãn ID + halo khi giữ bóng."""
    def __init__(self, side_m: float, color: QColor, robot_id: int):
        super().__init__()

        s_px = len_m2px(side_m)

        # Thân vuông, tâm tại (0,0)
        body = QGraphicsRectItem(-s_px / 2, -s_px / 2, s_px, s_px, self)
        body.setBrush(QBrush(color))
        body.setPen(QPen(Qt.black, 1.5))
        body.setZValue(1)

        # Mũi hướng (tam giác, trỏ về +x local)
        tri = QGraphicsPathItem(self)
        tri.setZValue(2)
        path = QPainterPath()
        path.moveTo(+0.45 * s_px, 0.0)
        path.lineTo(-0.15 * s_px, -0.22 * s_px)
        path.lineTo(-0.15 * s_px, +0.22 * s_px)
        path.closeSubpath()
        tri.setPath(path)
        tri.setBrush(QBrush(Qt.white))
        tri.setPen(QPen(Qt.NoPen))

        # Nhãn ID (nằm trên góc)
        label = QGraphicsTextItem(str(robot_id), self)
        label.setFont(QFont("Arial", 9, weight=QFont.Bold))
        label.setDefaultTextColor(Qt.black)
        label.setPos(-0.5 * s_px, -0.6 * s_px)  # đặt góc trên-trái
        label.setZValue(3)

        # Halo khi has_ball
        halo_r = 0.6 * s_px
        halo = QGraphicsEllipseItem(-halo_r, -halo_r, 2 * halo_r, 2 * halo_r, self)
        halo.setPen(QPen(QColor("yellow"), 2))
        halo.setBrush(QBrush(Qt.NoBrush))
        halo.setZValue(0)
        halo.setVisible(False)

        # Lưu refs
        self._s_px = s_px
        self._body = body
        self._tri = tri
        self._label = label
        self._halo = halo

        # Tâm quay tại tâm hình vuông
        self.setTransformOriginPoint(0.0, 0.0)

    def sync(self, x_m: float, y_m: float, theta_rad: float, active: bool, has_ball: bool):
        self.setPos(m2px(x_m, y_m))
        self.setRotation(-math.degrees(theta_rad))  # Qt dùng degree, CW
        self.setOpacity(1.0 if active else 0.3)
        self._halo.setVisible(has_ball)


class TeamGraphic:
    """
    Quản lý các RobotItem của một Team + nhãn action (không xoay cùng robot).
    - Không clear toàn bộ mỗi frame; chỉ thêm/xóa/sync theo robot_id.
    - Màu team truyền ở constructor.
    """
    def __init__(self, team: Team, scene: QGraphicsScene, color: QColor | Qt.GlobalColor):
        self.team = team
        self.scene = scene
        self.color = QColor(color)
        self.items: Dict[int, RobotItem] = {}                  # robot_id -> RobotItem
        self.labels: Dict[int, QGraphicsSimpleTextItem] = {}   # robot_id -> label action
        self._font = QFont("DejaVu Sans", 11)

    # Tạo item/label mới nếu robot mới xuất hiện; xóa nếu robot biến mất
    def ensure_items(self):
        current_ids = {r.robot_id for r in self.team.robots_list()}

        # remove những item/label không còn trong đội
        for rid in list(self.items.keys()):
            if rid not in current_ids:
                self.scene.removeItem(self.items[rid])
                del self.items[rid]
        for rid in list(self.labels.keys()):
            if rid not in current_ids:
                self.scene.removeItem(self.labels[rid])
                del self.labels[rid]

        # thêm item + label cho robot mới
        for r in self.team.robots_list():
            if r.robot_id not in self.items:
                item = RobotItem(side_m=r.side_len, color=self.color, robot_id=r.robot_id)
                self.items[r.robot_id] = item
                self.scene.addItem(item)
            if r.robot_id not in self.labels:
                lbl = QGraphicsSimpleTextItem("")   # nhãn action
                lbl.setFont(self._font)
                lbl.setBrush(QBrush(QColor("#ffffff")))
                lbl.setZValue(200)                  # nổi trên robot
                self.scene.addItem(lbl)
                self.labels[r.robot_id] = lbl

    def sync(self):
        self.ensure_items()
        for r in self.team.robots_list():
            # 1) đồng bộ robot item
            self.items[r.robot_id].sync(r.x, r.y, r.theta, r.active, r.has_ball)

            # 2) cập nhật nhãn action (không xoay)
            lbl = self.labels.get(r.robot_id)
            if not lbl:
                continue

            text = r.dbg_action or ""
            if lbl.text() != text:
                lbl.setText(text)

            # đặt nhãn ngay phía trên robot, canh giữa theo bề rộng text
            p = m2px(r.x, r.y)  # QPointF px
            br = lbl.boundingRect()
            offset_px = len_m2px(max(0.0, r.side_len * 0.5)) + 16  # nửa cạnh + 16px
            lbl.setPos(p.x() - br.width() / 2.0, p.y() - offset_px)

            # Ẩn/hiện theo trạng thái active
            lbl.setOpacity(1.0 if r.active else 0.35)

    def clear(self):
        for item in self.items.values():
            self.scene.removeItem(item)
        for lbl in self.labels.values():
            self.scene.removeItem(lbl)
        self.items.clear()
        self.labels.clear()
