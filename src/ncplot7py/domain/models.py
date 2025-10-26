"""Domain models for ncplot7py."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class NCNode:
    line: int
    cmd: str
    params: Dict[str, str]


