"""Shared serial reader — blocking and background modes with pause/resume/stop."""

import threading

import serial as pyserial

from brasa.core.output import error, print_stdout, status

# Lines matching these prefixes are suppressed when filter_repl=True
_REPL_NOISE = (">>>", "raw REPL; CTRL-B to exit", ">")


class SerialReader:
    """Unified serial reader for both `brasa serial` (blocking) and `brasa dev` (background)."""

    def __init__(
        self, port: str, baud: int = 115200, filter_repl: bool = False
    ) -> None:
        self._port = port
        self._baud = baud
        self._filter_repl = filter_repl

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Initially running (not paused)
        self._paused_ack = threading.Event()

        self._thread: threading.Thread | None = None
        self._serial: pyserial.Serial | None = None

    def _open(self) -> pyserial.Serial:
        """Open the serial port and store a reference."""
        self._serial = pyserial.Serial(self._port, self._baud, timeout=1)
        return self._serial

    def _close(self) -> None:
        """Close the serial port if open."""
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def _read_loop(self) -> None:
        """Core read loop shared by blocking and background modes."""
        try:
            conn = self._open()
        except pyserial.SerialException as exc:
            error(f"could not open {self._port}: {exc}")
            return

        try:
            while not self._stop_event.is_set():
                # Handle pause
                if not self._pause_event.is_set():
                    self._close()
                    self._paused_ack.set()
                    self._pause_event.wait()
                    if self._stop_event.is_set():
                        break
                    try:
                        conn = self._open()
                    except pyserial.SerialException as exc:
                        error(f"could not reopen {self._port}: {exc}")
                        return

                try:
                    raw = conn.readline()
                except pyserial.SerialException as exc:
                    error(f"serial read error: {exc}")
                    continue

                if not raw:
                    continue

                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                if self._filter_repl and line.startswith(_REPL_NOISE):
                    continue

                print_stdout(line)
        finally:
            self._close()

    def run_blocking(self) -> None:
        """Read serial lines in the main thread until KeyboardInterrupt. For `brasa serial`."""
        status("serial", f"reading from {self._port} at {self._baud} baud")
        try:
            self._read_loop()
        except KeyboardInterrupt:
            status("serial", "stopped")

    def start_background(self) -> None:
        """Start reading in a daemon thread. For `brasa dev`."""
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        """Pause reading and release the serial port (so mpremote can use it)."""
        self._paused_ack.clear()
        self._pause_event.clear()
        # Wait for the reader to actually release the port
        self._paused_ack.wait(timeout=1.2)

    def resume(self) -> None:
        """Resume reading after a pause."""
        self._pause_event.set()

    def stop(self) -> None:
        """Stop the reader permanently."""
        self._stop_event.set()
        self._pause_event.set()  # Unblock if paused
        if self._thread is not None:
            self._thread.join(timeout=3)
