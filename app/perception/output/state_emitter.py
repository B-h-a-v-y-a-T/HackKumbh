"""
State output serialization and emission.

Serializes PipelineOutput to JSON and sends to configured destination:
stdout, file, or callback function.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Callable, Dict, Optional

from app.perception.core.data_models import PipelineOutput

logger = logging.getLogger(__name__)


class StateEmitter:
    """
    Serializes and emits PipelineOutput.

    Supports:
    - stdout: Print JSON to console (one line per frame)
    - file: Append JSON lines to a file
    - callback: Call a function with the output dict
    - none: Suppress output (visualization-only mode)

    Args:
        format: Output format ("json").
        destination: Where to send output ("stdout", "none", file path, or "callback").
        callback: Custom callback function (when destination="callback").
        pretty: Use pretty-printed JSON (slower, for debugging).
    """

    def __init__(
        self,
        format: str = "json",
        destination: str = "none",
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        pretty: bool = False,
    ):
        self.format = format
        self.destination = destination
        self.callback = callback
        self.pretty = pretty
        self._file_handle = None
        self._frame_count = 0

    def emit(self, output: PipelineOutput):
        """
        Serialize and emit the pipeline output.

        Args:
            output: Complete pipeline output for one frame.
        """
        self._frame_count += 1

        if self.destination == "none":
            return

        data = output.to_dict()

        if self.format == "json":
            self._emit_json(data)
        else:
            logger.warning("Unknown output format: %s", self.format)

    def _emit_json(self, data: Dict[str, Any]):
        """Emit as JSON."""
        try:
            if self.pretty:
                json_str = json.dumps(data, indent=2, default=str)
            else:
                json_str = json.dumps(data, separators=(",", ":"), default=str)
        except (TypeError, ValueError) as e:
            logger.error("JSON serialization error: %s", e)
            return

        if self.destination == "stdout":
            print(json_str, flush=True)

        elif self.destination == "callback":
            if self.callback is not None:
                try:
                    self.callback(data)
                except Exception as e:
                    logger.error("Output callback error: %s", e)

        else:
            # File destination
            try:
                if self._file_handle is None:
                    self._file_handle = open(self.destination, "a", encoding="utf-8")
                self._file_handle.write(json_str + "\n")
                self._file_handle.flush()
            except IOError as e:
                logger.error("File write error (%s): %s", self.destination, e)

    @property
    def frames_emitted(self) -> int:
        return self._frame_count

    def close(self):
        """Close any open file handles."""
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None

    def __del__(self):
        self.close()
