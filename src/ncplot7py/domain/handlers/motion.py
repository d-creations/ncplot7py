"""Motion handler for G1/G2/G3 moves located in domain.handlers.

This is the domain-located copy of the motion handler implementation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ncplot7py.domain.cnc_state import CNCState
from ncplot7py.shared.nc_nodes import NCCommandNode
from ncplot7py.domain.exec_chain import Handler
from ncplot7py.shared.point import Point


def _to_float(v: Optional[str], default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


class MotionHandler(Handler):
    """Handle G0/G1/G2/G3 interpolation.

    Produces (list[Point], duration_seconds) when motion occurs, otherwise
    delegates to next handler.
    """

    def __init__(self, next_handler: Optional[Handler] = None, max_segment: float = 0.5):
        super().__init__(next_handler=next_handler)
        self.max_segment = float(max_segment)

    def handle(self, node: NCCommandNode, state: CNCState) -> Tuple[Optional[List[Point]], Optional[float]]:
        # detect motion codes
        interp_mode = None  # 'G00','G01','G02','G03'
        for g in node.g_code:
            if g.upper() in ("G00", "G0", "G0 "):
                interp_mode = "G00"
            if g.upper() in ("G01", "G1"):
                interp_mode = "G01"
            if g.upper() in ("G02", "G2"):
                interp_mode = "G02"
            if g.upper() in ("G03", "G3"):
                interp_mode = "G03"

        if interp_mode is None:
            return super().handle(node, state)

        # Resolve start and end positions using state.resolve_target
        start = state.axes.copy()
        # build target spec from parameters: X,Y,Z or U,V,W for relative
        target_spec: Dict[str, float] = {}
        absolute_mode = True
        # check distance mode modal (G90/G91)
        dm = state.get_modal("distance")
        if dm and dm.upper() == "G91":
            absolute_mode = False

        for k, v in node.command_parameter.items():
            key = k.upper()
            if key in ("X", "Y", "Z", "A", "B", "C"):
                target_spec[key] = _to_float(v)
            elif key in ("U", "V", "W"):
                # relative axis spec; treat as delta
                # map UVW to XYZ
                mapped = {"U": "X", "V": "Y", "W": "Z"}[key]
                target_spec[mapped] = _to_float(v)
            # I,J,K,R,F handled later

        # get resolved absolute targets
        resolved = state.resolve_target(target_spec, absolute=absolute_mode)

        # interpolation parameters
        params = {k.upper(): _to_float(v) for k, v in node.command_parameter.items()}

        if interp_mode == "G01" or interp_mode == "G00":
            points, duration = self._linear_interpolate(start, resolved, state)
        elif interp_mode in ("G02", "G03"):
            cw = interp_mode == "G02"
            points, duration = self._circular_interpolate(start, resolved, params, state, cw)
        else:
            return super().handle(node, state)

        # update state axes to endpoint
        state.update_axes(resolved)

        return points, duration

    def _linear_interpolate(self, start: Dict[str, float], end: Dict[str, float], state: CNCState) -> Tuple[List[Point], float]:
        # compute distance in XYZ space
        axes = ("X", "Y", "Z")
        dist = state.compute_distance(start, end, axes=list(axes))
        if dist <= 0.0:
            # no motion
            p = Point(x=end.get("X", 0.0), y=end.get("Y", 0.0), z=end.get("Z", 0.0),
                      a=end.get("A", 0.0), b=end.get("B", 0.0), c=end.get("C", 0.0))
            return [p], 0.0

        # determine number of segments
        n = max(1, int(math.ceil(dist / self.max_segment)))
        # compute duration using feed rate (assume feed_rate in units per minute)
        feed = state.feed_rate or 1.0
        # convert feed (mm/min) -> mm/s
        feed_mm_s = float(feed) / 60.0
        duration = dist / feed_mm_s if feed_mm_s > 0 else 0.0

        points: List[Point] = []
        for i in range(1, n + 1):
            t = i / n
            x = start.get("X", 0.0) + (end.get("X", start.get("X", 0.0)) - start.get("X", 0.0)) * t
            y = start.get("Y", 0.0) + (end.get("Y", start.get("Y", 0.0)) - start.get("Y", 0.0)) * t
            z = start.get("Z", 0.0) + (end.get("Z", start.get("Z", 0.0)) - start.get("Z", 0.0)) * t
            a = end.get("A", start.get("A", 0.0))
            b = end.get("B", start.get("B", 0.0))
            c = end.get("C", start.get("C", 0.0))
            points.append(Point(x=x, y=y, z=z, a=a, b=b, c=c))
        return points, duration

    def _circular_interpolate(self, start: Dict[str, float], end: Dict[str, float], params: Dict[str, float], state: CNCState, cw: bool) -> Tuple[List[Point], float]:
        # Only implement XY-plane arcs for now (common case). Use I,J center offsets or R radius.
        sx = start.get("X", 0.0)
        sy = start.get("Y", 0.0)
        ex = end.get("X", sx)
        ey = end.get("Y", sy)

        # center
        if "I" in params or "J" in params:
            ix = params.get("I", 0.0)
            jy = params.get("J", 0.0)
            cx = sx + ix
            cy = sy + jy
        elif "R" in params and params.get("R", 0.0) != 0.0:
            # derive center from radius — choose the smaller arc by default
            r = params.get("R", 0.0)
            # compute midpoint
            mx = (sx + ex) / 2.0
            my = (sy + ey) / 2.0
            dx = ex - sx
            dy = ey - sy
            d2 = dx * dx + dy * dy
            if d2 == 0.0:
                raise ValueError("Invalid arc with zero chord length")
            h = math.sqrt(max(0.0, r * r - d2 / 4.0)) / math.sqrt(d2)
            # two possible centers; choose one based on cw flag
            cx1 = mx - h * dy
            cy1 = my + h * dx
            cx2 = mx + h * dy
            cy2 = my - h * dx
            cx, cy = (cx1, cy1) if cw else (cx2, cy2)
        else:
            # cannot compute arc center
            raise ValueError("Arc requires I/J or R parameter")

        # compute start and end angles
        a0 = math.atan2(sy - cy, sx - cx)
        a1 = math.atan2(ey - cy, ex - cx)
        # sweep angle
        da = a1 - a0
        if cw and da > 0:
            da -= 2 * math.pi
        if (not cw) and da < 0:
            da += 2 * math.pi

        arc_length = abs(da) * math.hypot(sx - cx, sy - cy)
        # n segments
        n = max(2, int(math.ceil(arc_length / self.max_segment)))

        # duration using feed rate
        feed = state.feed_rate or 1.0
        feed_mm_s = float(feed) / 60.0
        duration = arc_length / feed_mm_s if feed_mm_s > 0 else 0.0

        points: List[Point] = []
        for i in range(1, n + 1):
            t = i / n
            theta = a0 + da * t
            x = cx + math.cos(theta) * math.hypot(sx - cx, sy - cy)
            y = cy + math.sin(theta) * math.hypot(sx - cx, sy - cy)
            z = start.get("Z", 0.0) + (end.get("Z", start.get("Z", 0.0)) - start.get("Z", 0.0)) * t
            a = end.get("A", start.get("A", 0.0))
            b = end.get("B", start.get("B", 0.0))
            c = end.get("C", start.get("C", 0.0))
            points.append(Point(x=x, y=y, z=z, a=a, b=b, c=c))

        return points, duration


__all__ = ["MotionHandler", "Point"]
