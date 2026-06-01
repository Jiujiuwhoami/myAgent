"""Compatibility namespace package for myAgent."""

from __future__ import annotations

from pathlib import Path

__version__ = "2.1.0"

_PACKAGE_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = str(_PACKAGE_ROOT.parent)

if _PROJECT_ROOT not in __path__:
    __path__.append(_PROJECT_ROOT)

__all__ = ["__version__"]
