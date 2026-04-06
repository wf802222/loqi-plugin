"""Server lifecycle management — PID files and auto-shutdown."""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path
from threading import Timer

PID_FILE = Path.home() / ".loqi-server.pid"
DEFAULT_IDLE_TIMEOUT = 1800  # 30 minutes


def write_pid() -> None:
    """Write current PID to the PID file."""
    PID_FILE.write_text(str(os.getpid()))


def read_pid() -> int | None:
    """Read PID from file. Returns None if not found or stale."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process is actually running
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                kernel32.CloseHandle(handle)
                return pid
            return None
        else:
            os.kill(pid, 0)  # Signal 0 = check existence
            return pid
    except (ValueError, OSError, ProcessLookupError):
        return None


def remove_pid() -> None:
    """Remove PID file on shutdown."""
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


class IdleShutdown:
    """Auto-shutdown the server after a period of inactivity."""

    def __init__(self, timeout: int = DEFAULT_IDLE_TIMEOUT):
        self._timeout = timeout
        self._timer: Timer | None = None
        self.reset()

    def reset(self) -> None:
        """Reset the idle timer (call on each request)."""
        if self._timer:
            self._timer.cancel()
        self._timer = Timer(self._timeout, self._shutdown)
        self._timer.daemon = True
        self._timer.start()

    def _shutdown(self) -> None:
        """Perform clean shutdown."""
        remove_pid()
        os._exit(0)

    def cancel(self) -> None:
        """Cancel the timer (for manual shutdown)."""
        if self._timer:
            self._timer.cancel()
