"""Unit tests for brasa.core.serial — SerialReader."""

import threading
import time
from unittest.mock import MagicMock, patch

import serial as pyserial

from brasa.core.serial import SerialReader


def _make_mock_serial(
    lines: list[bytes], done_event: threading.Event | None = None
) -> MagicMock:
    """Create a mock serial that yields lines then signals done_event."""
    mock = MagicMock()
    mock.is_open = True
    remaining = list(lines)
    exhausted = threading.Event()

    def _readline() -> bytes:
        if remaining:
            line = remaining.pop(0)
            if not remaining and done_event is not None:
                done_event.set()
            return line
        exhausted.set()
        # Block briefly; the reader thread will be interrupted by stop_event
        time.sleep(0.01)
        return b""

    mock.readline.side_effect = _readline
    mock._exhausted = exhausted
    return mock


class TestSerialReader:
    """Tests for SerialReader."""

    @patch("brasa.core.serial.print_stdout")
    @patch("brasa.core.serial.pyserial.Serial")
    def test_reads_lines_and_prints(
        self, mock_serial_cls: MagicMock, mock_print: MagicMock
    ) -> None:
        """Reader reads lines and prints them to stdout."""
        printed = threading.Event()
        call_count = 0
        original_side_effect = mock_print.side_effect

        def _on_print(*args: object, **kwargs: object) -> None:
            nonlocal call_count
            if original_side_effect:
                original_side_effect(*args, **kwargs)
            call_count += 1
            if call_count >= 2:
                printed.set()

        mock_print.side_effect = _on_print

        mock_conn = _make_mock_serial([b"hello\r\n", b"world\r\n"])
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader("/dev/ttyUSB0", baud=115200)
        try:
            reader.start_background()
            assert printed.wait(timeout=2), "print_stdout was not called twice in time"
        finally:
            reader.stop()

        mock_serial_cls.assert_called_once_with("/dev/ttyUSB0", 115200, timeout=1)
        mock_print.assert_any_call("hello")
        mock_print.assert_any_call("world")

    @patch("brasa.core.serial.print_stdout")
    @patch("brasa.core.serial.pyserial.Serial")
    def test_filter_repl_skips_noise(
        self, mock_serial_cls: MagicMock, mock_print: MagicMock
    ) -> None:
        """filter_repl=True suppresses REPL noise lines."""
        printed = threading.Event()

        def _on_print(*args: object, **kwargs: object) -> None:
            printed.set()

        mock_print.side_effect = _on_print

        mock_conn = _make_mock_serial(
            [
                b">>> \r\n",
                b"real output\r\n",
                b"raw REPL; CTRL-B to exit\r\n",
                b"> \r\n",
            ]
        )
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader("/dev/ttyUSB0", filter_repl=True)
        try:
            reader.start_background()
            assert printed.wait(timeout=2), "print_stdout was not called in time"
            # Wait for mock to have consumed remaining lines
            assert mock_conn._exhausted.wait(timeout=2), (
                "mock did not exhaust all lines"
            )
        finally:
            reader.stop()

        # Only "real output" should have been printed
        mock_print.assert_called_once_with("real output")

    @patch("brasa.core.serial.pyserial.Serial")
    def test_pause_closes_port_resume_reopens(self, mock_serial_cls: MagicMock) -> None:
        """pause() closes the serial port, resume() reopens it."""
        mock_conn = _make_mock_serial([])
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader("/dev/ttyUSB0")
        try:
            reader.start_background()

            reader.pause()
            # pause() internally waits on _paused_ack, so port is closed now
            mock_conn.close.assert_called()

            reader.resume()
            # Poll briefly for the Serial constructor to be called again
            deadline = time.monotonic() + 2
            while mock_serial_cls.call_count < 2 and time.monotonic() < deadline:
                time.sleep(0.01)

            assert mock_serial_cls.call_count >= 2
        finally:
            reader.stop()

    @patch("brasa.core.serial.pyserial.Serial")
    def test_stop_exits_read_loop(self, mock_serial_cls: MagicMock) -> None:
        """stop() causes the read loop to exit and thread to finish."""
        mock_conn = _make_mock_serial([])
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader("/dev/ttyUSB0")
        reader.start_background()
        assert reader._thread is not None
        assert reader._thread.is_alive()

        reader.stop()
        # stop() joins the thread, so it should be finished
        assert not reader._thread.is_alive()

    @patch("brasa.core.serial.error")
    @patch("brasa.core.serial.pyserial.Serial")
    def test_serial_exception_logged_not_crash(
        self, mock_serial_cls: MagicMock, mock_error: MagicMock
    ) -> None:
        """SerialException during read is caught and logged."""
        mock_conn = MagicMock()
        mock_conn.is_open = True
        mock_conn.readline.side_effect = pyserial.SerialException("device disconnected")
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader("/dev/ttyUSB0")
        try:
            reader.start_background()
            # After 3 consecutive errors the thread exits on its own
            assert reader._thread is not None
            reader._thread.join(timeout=2)
        finally:
            reader.stop()

        mock_error.assert_called()
        assert "serial read failed" in mock_error.call_args[0][0]

    @patch("brasa.core.serial.pyserial.Serial")
    def test_start_background_creates_daemon_thread(
        self, mock_serial_cls: MagicMock
    ) -> None:
        """start_background() starts a daemon thread."""
        mock_conn = _make_mock_serial([])
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader("/dev/ttyUSB0")
        try:
            reader.start_background()
            assert reader._thread is not None
            assert reader._thread.daemon is True
            assert reader._thread.is_alive()
        finally:
            reader.stop()

    @patch("brasa.core.serial.error")
    @patch("brasa.core.serial.pyserial.Serial")
    def test_open_failure_logs_error(
        self, mock_serial_cls: MagicMock, mock_error: MagicMock
    ) -> None:
        """SerialException on open is caught and logged."""
        mock_serial_cls.side_effect = pyserial.SerialException("port not found")

        reader = SerialReader("/dev/ttyUSB0")
        reader.start_background()
        # Thread exits almost immediately on open failure
        assert reader._thread is not None
        reader._thread.join(timeout=2)

        mock_error.assert_called()
        assert "could not open" in mock_error.call_args[0][0]
