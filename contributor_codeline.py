"""Contributor codeline examples.

This module contains a minimal, stdlib-only example showing a write-only helper
function. It includes documentation and doctest examples so CI can run
`python -m doctest` against it.

Guidelines followed:
- Use only Python standard library.
- Keep examples deterministic and self-cleaning (remove temporary files).
- Provide a small doctest demonstrating usage.

"""
from __future__ import annotations

from pathlib import Path
from typing import Union


def write_text(path: Union[str, Path], text: str, append: bool = False) -> None:
    """Write text to a file using only standard library functions.

    Args:
        path: File path to write to. Can be a string or Path.
        text: Text content to write.
        append: If True, append to the file; otherwise overwrite.

    Returns:
        None

    Doctest example (runs deterministically):

    >>> # create a small file, read it back, then remove it
    >>> write_text('tmp_test.txt', 'hello')
    >>> open('tmp_test.txt', 'r', encoding='utf-8').read()
    'hello'
    >>> # clean up
    >>> import os
    >>> os.remove('tmp_test.txt')

    """
    mode = 'a' if append else 'w'
    p = Path(path)
    # Ensure parent directory exists when a Path with directories is provided
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)

    # Use explicit encoding for reproducible behavior across platforms
    with p.open(mode, encoding='utf-8') as fh:
        fh.write(text)


__all__ = ["write_text"]
