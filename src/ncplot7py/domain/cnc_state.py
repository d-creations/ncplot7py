"""CNCState model moved into domain package.

Same content as the previous `shared.cnc_state` but placed under domain to
reflect that this is core domain model logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from copy import deepcopy
from typing import Dict, List, Optional, Tuple


AxisName = str
Numeric = float


@dataclass
class CNCState:
    """Represents the machine state during NC interpretation.

    Key pieces of data:
    - modal_groups: mapping of modal group name -> active code (e.g. 'G0', 'G1')
    - axes: mapping axis name -> current coordinate (e.g. 'X': 0.0)
    - offsets: tool/cs offsets applied to axes (same shape as `axes`)
    - feed_rate: current feed value (units depend on `units` modal)
    - spindle_speed: current spindle speed
    - tool_radius: numeric tool radius (for compensation)
    - parameters: generic user/parameter variables (#-style) stored as dict
    - extra: place to store vendor-specific flags (e.g., polar mode axis name)

    Methods on the state are intentionally small and side-effecting; callers
    should control transactional behaviour (clone/restore) when needed.
    """

    # Modal groups — keys are group identifiers (string), values the active code
    modal_groups: Dict[str, Optional[str]] = field(default_factory=dict)

    # Axis positions — use dict to support arbitrary axis sets (X,Y,Z,A,B,C...)
    axes: Dict[AxisName, Numeric] = field(default_factory=lambda: {"X": 0.0, "Y": 0.0, "Z": 0.0})

    # Offset axes (tool length, coordinate system offsets, etc.)
    offsets: Dict[AxisName, Numeric] = field(default_factory=dict)

    # Multipliers and override feeds per axis (e.g., for scaling or axis-specific feed)
    axis_multipliers: Dict[AxisName, Numeric] = field(default_factory=dict)
    axis_override_feeds: Dict[AxisName, Numeric] = field(default_factory=dict)

    # Motion & tooling fields
    feed_rate: Optional[Numeric] = None
    spindle_speed: Optional[Numeric] = None
    tool_radius: Optional[Numeric] = None
    tool_quadrant: Optional[int] = None

    # Program parameters / variables (#500 style) and DDDP table if present
    parameters: Dict[str, Numeric] = field(default_factory=dict)
    dddp_set: Dict[str, Numeric] = field(default_factory=dict)

    # Misc
    line_number: int = 0
    loop_command: List[str] = field(default_factory=list)
    extra: Dict[str, object] = field(default_factory=dict)

    def clone(self) -> "CNCState":
        """Return a deep copy of the state for transactional updates."""
        return deepcopy(self)

    def as_dict(self) -> Dict:
        """Serialize to a plain dict (helpful for debugging/tests)."""
        return asdict(self)

    # --- axis helpers -------------------------------------------------
    def get_axis(self, name: AxisName) -> Numeric:
        return self.axes.get(name, 0.0)

    def set_axis(self, name: AxisName, value: Numeric) -> None:
        self.axes[name] = float(value)

    def update_axes(self, updates: Dict[AxisName, Numeric]) -> None:
        for k, v in updates.items():
            self.set_axis(k, float(v))

    def apply_offsets(self) -> Dict[AxisName, Numeric]:
        """Return axes with offsets applied (doesn't mutate state)."""
        result = {}
        for ax, pos in self.axes.items():
            off = self.offsets.get(ax, 0.0)
            result[ax] = pos + off
        return result

    # --- modal helpers -----------------------------------------------
    def set_modal(self, group: str, code: Optional[str]) -> None:
        """Set the active code for a modal group."""
        self.modal_groups[group] = code

    def get_modal(self, group: str) -> Optional[str]:
        return self.modal_groups.get(group)

    # --- parameter helpers -------------------------------------------
    def set_parameter(self, name: str, value: Numeric) -> None:
        self.parameters[name] = float(value)

    def get_parameter(self, name: str, default: Optional[Numeric] = None) -> Optional[Numeric]:
        return self.parameters.get(name, default)

    # --- coordinate resolution ---------------------------------------
    def resolve_target(self, target_spec: Dict[AxisName, Numeric], absolute: bool = True) -> Dict[AxisName, Numeric]:
        """Given a target spec (possibly partial), return resolved absolute coords.

        If `absolute` is False, the values in `target_spec` are treated as deltas
        and applied to the current axis positions.
        """
        resolved: Dict[AxisName, Numeric] = {}
        if absolute:
            # start with current axes, then update with provided values
            for ax in set(list(self.axes.keys()) + list(target_spec.keys())):
                if ax in target_spec:
                    resolved[ax] = float(target_spec[ax])
                else:
                    resolved[ax] = self.get_axis(ax)
        else:
            for ax in set(list(self.axes.keys()) + list(target_spec.keys())):
                delta = float(target_spec.get(ax, 0.0))
                resolved[ax] = self.get_axis(ax) + delta
        return resolved

    # --- small utility ------------------------------------------------
    def compute_distance(self, a: Dict[AxisName, Numeric], b: Dict[AxisName, Numeric], axes: Optional[List[AxisName]] = None) -> float:
        """Euclidean distance between two axis positions using given axes list."""
        if axes is None:
            axes = list(set(list(a.keys()) + list(b.keys())))
        s = 0.0
        for ax in axes:
            s += (a.get(ax, 0.0) - b.get(ax, 0.0)) ** 2
        return float(s ** 0.5)


__all__ = ["CNCState"]
