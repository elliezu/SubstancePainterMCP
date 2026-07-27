"""Backward-compatible imports for the old module path."""

from substance_painter_mcp.client import (
    PainterConnectionError,
    PainterHTTPError,
    PainterRemote,
    PainterRemoteConfig,
    PainterRemoteError,
    PainterScriptError,
)

__all__ = [
    "PainterConnectionError",
    "PainterHTTPError",
    "PainterRemote",
    "PainterRemoteConfig",
    "PainterRemoteError",
    "PainterScriptError",
]
