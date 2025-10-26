"""Simple registry for parsers, machines and plotters.

This keeps the example small; for production consider entry_points or a plugin
system via importlib.metadata.
"""
from __future__ import annotations

from typing import Dict, Type


class Registry:
    def __init__(self):
        self._data: Dict[str, Dict[str, Type]] = {}

    def register(self, kind: str, name: str, cls: Type) -> None:
        self._data.setdefault(kind, {})[name] = cls

    def get(self, kind: str, name: str):
        return self._data.get(kind, {}).get(name)


registry = Registry()

# Eagerly import built-in adapters so they register themselves
try:
    from ncplot7py.infrastructure.parsers.gcode_parser import register as _reg_p
    from ncplot7py.infrastructure.machines.generic_machine import register as _reg_m
    from ncplot7py.infrastructure.plotters.matplotlib_plotter import register as _reg_pl

    _reg_p(registry)
    _reg_m(registry)
    _reg_pl(registry)
except Exception:
    # Keep registry import safe even if optional deps are missing
    try:
        _reg_p(registry)
        _reg_m(registry)
    except Exception:
        pass
