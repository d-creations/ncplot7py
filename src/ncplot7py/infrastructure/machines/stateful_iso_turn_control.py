"""A Stateful NC control implementation that wires the execution chain.

This control composes the small Chain-of-Responsibility handlers (G50/G28
handler and MotionHandler) and implements the control interface expected by
`NCExecutionEngine` (`run_nc_code_list`, `get_tool_path`, etc.).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Sequence

from ncplot7py.interfaces.BaseNCCanal import NCControl as BaseNCControlInterface
from ncplot7py.interfaces.BaseNCControl import NCCanal as BaseNCCanalInterface

from ncplot7py.domain.handlers.gcode_group0 import GCodeGroup0ExecChainLink
from ncplot7py.domain.handlers.motion import MotionHandler, Point
from ncplot7py.domain.cnc_state import CNCState
from ncplot7py.shared.nc_nodes import NCCommandNode


class StatefulIsoTurnCanal(BaseNCCanalInterface):
    """Per-canal object implementing the `NCCanal` interface.

    The canal owns its own CNCState and a short chain (G50/G28 -> Motion)
    instance used to interpret NC nodes for that canal.
    """

    def __init__(self, name: str, init_state: Optional[CNCState] = None):
        self._name = name
        self._state = init_state or CNCState()
        self._chain = GCodeGroup0ExecChainLink(next_handler=MotionHandler())
        self._nodes: List[NCCommandNode] = []
        self._tool_path: List[Tuple[List[Point], float]] = []

    def get_name(self) -> str:
        return self._name

    def run_nc_code_list(self, linked_code_list: List[NCCommandNode]) -> None:
        self._nodes = list(linked_code_list)
        self._tool_path = []
        for node in self._nodes:
            pts, dur = self._chain.handle(node, self._state)
            if pts is not None:
                self._tool_path.append((pts, dur or 0.0))

    def get_tool_path(self) -> List[Tuple[List[Point], float]]:
        return self._tool_path

    def get_exec_nodes(self) -> List[NCCommandNode]:
        return self._nodes


class StatefulIsoTurnNCControl(BaseNCControlInterface):
    """Control managing multiple `StatefulIsoTurnCanal` instances.

    Implements the `NCControl` abstract interface while delegating per-canal
    execution to `StatefulIsoTurnCanal` objects.
    """

    def __init__(self, count_of_canals: int = 1, canal_names: Optional[Sequence[str]] = None, init_nc_states: Optional[Sequence[CNCState]] = None) -> None:
        # create canal objects
        self.count_of_canals = int(count_of_canals)
        names = []
        if canal_names is None:
            names = [f"C{i+1}" for i in range(self.count_of_canals)]
        else:
            if isinstance(canal_names, str):
                # single name given -> expand
                names = [canal_names for _ in range(self.count_of_canals)]
            else:
                names = list(canal_names)

        init_states = list(init_nc_states) if init_nc_states is not None else [None] * self.count_of_canals

        self._canals: Dict[int, StatefulIsoTurnCanal] = {}
        for idx in range(self.count_of_canals):
            init_state = init_states[idx] if idx < len(init_states) else None
            self._canals[idx + 1] = StatefulIsoTurnCanal(names[idx], init_state)

    def get_canal_name(self, canal: int) -> str:
        c = self._canals.get(canal)
        return c.get_name() if c is not None else f"C{canal}"

    def run_nc_code_list(self, linked_code_list: List[NCCommandNode], canal: int) -> None:
        c = self._canals.get(canal)
        if c is None:
            raise IndexError(f"Canal {canal} not configured")
        c.run_nc_code_list(linked_code_list)

    def get_tool_path(self, canal: int) -> List[Tuple[List[Point], float]]:
        c = self._canals.get(canal)
        if c is None:
            return []
        return c.get_tool_path()

    def get_exected_nodes(self, canal: int) -> List[NCCommandNode]:
        c = self._canals.get(canal)
        if c is None:
            return []
        return c.get_exec_nodes()

    def get_canal_count(self) -> int:
        return self.count_of_canals

    def synchro_points(self, tool_paths, nodes):
        # placeholder: no synchronization in this simple control
        return None


__all__ = ["StatefulIsoTurnNCControl"]
