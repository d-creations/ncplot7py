"""A Stateful NC control implementation that wires the execution chain.

This control composes the small Chain-of-Responsibility handlers (G50/G28
handler and MotionHandler) and implements the control interface expected by
`NCExecutionEngine` (`run_nc_code_list`, `get_tool_path`, etc.).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Sequence
import re

from ncplot7py.interfaces.BaseNCCanal import NCControl as BaseNCControlInterface
from ncplot7py.interfaces.BaseNCControl import NCCanal as BaseNCCanalInterface

from ncplot7py.domain.handlers.gcode_group0 import GCodeGroup0ExecChainLink
from ncplot7py.domain.handlers.motion import MotionHandler
from ncplot7py.domain.handlers.variable import VariableHandler
from ncplot7py.domain.handlers.control_flow import ControlFlowHandler
from ncplot7py.domain.handlers.gcode_group2 import GCodeGroup2ExecChainLink
from ncplot7py.shared.point import Point
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
        # Chain: variables -> control flow -> group2 (speed mode) -> group0 -> motion
        motion = MotionHandler()
        gcode0 = GCodeGroup0ExecChainLink(next_handler=motion)
        gcode2 = GCodeGroup2ExecChainLink(next_handler=gcode0)
        # Group5 handles feed mode (G98/G99) and sits between group2 and group0
        try:
            from ncplot7py.domain.handlers.gcode_group5 import GCodeGroup5ExecChainLink
            gcode5 = GCodeGroup5ExecChainLink(next_handler=gcode2)
            control = ControlFlowHandler(next_handler=gcode5)
        except Exception:
            # Fallback: if import fails, wire control directly to group2
            control = ControlFlowHandler(next_handler=gcode2)
        variable = VariableHandler(next_handler=control)
        self._chain = variable
        # keep reference to control handler so we can provide node maps per-run
        self._control_handler = control
        self._nodes: List[NCCommandNode] = []
        self._tool_path: List[Tuple[List[Point], float]] = []

    def get_name(self) -> str:
        return self._name

    def run_nc_code_list(self, linked_code_list: List[NCCommandNode]) -> None:
        # convert to list and set up linked pointers so control flow handlers
        # can jump between nodes by manipulating `_next_ncCode`.
        self._nodes = list(linked_code_list)
        self._tool_path = []

        # link nodes in forward/backward direction
        for i in range(len(self._nodes) - 1):
            self._nodes[i]._next_ncCode = self._nodes[i + 1]
            self._nodes[i + 1]._before_ncCode = self._nodes[i]

        # build lookup maps for labels and DO/END tokens to help control flow
        n_map = {}
        do_map = {}
        end_map = {}
        for nd in self._nodes:
            try:
                nval = nd.command_parameter.get("N")
            except Exception:
                nval = None
            if nval is not None:
                try:
                    key = float(nval)
                    n_map[key] = nd
                except Exception:
                    pass
            # detect DO/END labels inside loop_command
            lc = nd.loop_command
            if lc:
                # DO labels
                for m in re.findall(r"DO(\d+)", lc):
                    do_map.setdefault(m, []).append(nd)
                for m in re.findall(r"END(\d+)", lc):
                    end_map.setdefault(m, []).append(nd)

        # provide maps to control handler (if present)
        try:
            self._control_handler._n_map = n_map
            self._control_handler._do_map = do_map
            self._control_handler._end_map = end_map
            self._control_handler._nodes = self._nodes
            # reset any existing loop counters for this run
            self._control_handler._loop_counters = {}
        except Exception:
            pass

        # execute following `_next_ncCode` pointers; bound iterations to
        # avoid infinite loops. Handlers may update `_next_ncCode` to jump.
        node = self._nodes[0] if len(self._nodes) > 0 else None
        max_steps = max(10000, len(self._nodes) * 100)
        steps = 0
        while node is not None and steps < max_steps:
            pts, dur = self._chain.handle(node, self._state)
            if pts is not None:
                self._tool_path.append((pts, dur or 0.0))
            # follow pointer (handlers may have updated it)
            next_node = getattr(node, "_next_ncCode", None)
            # if next_node is same as current, break to avoid tight loop
            if next_node is node:
                break
            node = next_node
            steps += 1

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
