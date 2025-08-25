# utils/geom.py
from __future__ import annotations
from typing import Optional
from PyQt5.QtCore import QPointF

# các hằng theo *m* và px
from config.constants import FIELD_W, FIELD_H, SCALE, MARGIN

def m2px(x_m: float, y_m: float, *, scale: Optional[float] = None) -> QPointF:
    """
    World (m, gốc giữa, +y lên) -> Pixel (gốc trên-trái, +y xuống)
    - center_px = (MARGIN + FIELD_W/2 * SCALE,  MARGIN + FIELD_H/2 * SCALE)
    - x_px = center_x + x_m * SCALE
    - y_px = center_y - y_m * SCALE
    """
    s = SCALE if scale is None else scale
    cx = MARGIN + (FIELD_W * s) * 0.5
    cy = MARGIN + (FIELD_H * s) * 0.5
    return QPointF(cx + x_m * s, cy - y_m * s)

def len_m2px(l_m: float, *, scale: Optional[float] = None) -> float:
    s = SCALE if scale is None else scale
    return l_m * s

# (nếu cần chiều ngược lại)
def px2m(x_px: float, y_px: float, *, scale: Optional[float] = None):
    s = SCALE if scale is None else scale
    cx = MARGIN + (FIELD_W * s) * 0.5
    cy = MARGIN + (FIELD_H * s) * 0.5
    return ((x_px - cx) / s, -(y_px - cy) / s)
