"""Unit tests for brasa.core.serial — SerialReader."""

import time
from unittest.mock import MagicMock, patch

import serial as pyserial

from brasa.core.serial import SerialReader


def _make_mock_serial(lines: list[bytes]) -> MagicMock:
    """Create a mock serial object that returns *lines* then blocks."""
    mock = MagicMock()
    mock.is_open = True

    remaining = list(lines)

    def _readline() -> bytes:
        if remaining:
            return remaining.pop(0)
        # Block briefly then return empty (simulates timeout)
        time.sleep(0.05)
        return b""

    mock.readline.side_effect = _readline
    return mock


class TestSerialReader:
    """Tests for SerialReader."""

    @patch("brasa.core.serial.pyserial.Serial")
    def test_reads_lines_and_prints(self, mock_serial_cls: MagicMock) -> None:
        """Reader reads lines and prints them to stdout."""
        mock_conn = _make_mock_serial([b"hello\r\n", b"world\r\n"])
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader("/dev/ttyUSB0", baud=115200)
        reader.start_background()

        # Give the thread time to read
        time.sleep(0.3)
        reader.stop()

        mock_serial_cls.assert_called_once_with("/dev/ttyUSB0", 115200, timeout=1)
        assert mock_conn.readline.call_count >= 2

    @patch("brasa.core.serial.print_stdout")
    @patch("brasa.core.serial.pyserial.Serial")
    def test_filter_repl_skips_noise(
        self, mock_serial_cls: MagicMock, mock_print: MagicMock
    ) -> None:
        """filter_repl=True suppresses REPL noise lines."""
        mock_conn = _make_mock_serial(
            [b">>> \r\n", b"real output\r\n", b"raw REPL; CTRL-B to exit\r\n", b"> \r\n"]
        )
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader("/dev/ttyUSB0", filter_repl=True)
        reader.start_background()
        time.sleep(0.3)
        reader.stop()

        # Only "real output" should have been printed
        mock_print.assert_called_once_with("real output")

    @patch("brasa.core.serial.pyserial.Serial")
    def test_pause_closes_port_resume_reopens(self, mock_serial_cls: MagicMock) -> None:
        """pause() closes the serial port, resume() reopens it."""
        mock_conn = _make_mock_serial([])
        # readline blocks indefinitely returning empty bytes
        mock_conn.readline.side_effect = lambda: (time.sleep(0.05) or b"")
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader("/dev/ttyUSB0")
        reader.start_background()
        time.sleep(0.2)

        reader.pause()
        # Port should have been closed
        mock_conn.close.assert_called()

        reader.resume()
        time.sleep(0.2)

        # Serial constructor called again on resume
        assert mock_serial_cls.call_count >= 2

        reader.stop()

    @patch("brasa.core.serial.pyserial.Serial")
    def test_stop_exits_read_loop(self, mock_serial_cls: MagicMock) -> None:
        """stop() causes the read loop to exit and thread to finish."""
        mock_conn = _make_mock_serial([])
        mock_conn.readline.side_effect = lambda: (time.sleep(0.05) or b"")
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader("/dev/ttyUSB0")
        reader.start_background()
        assert reader._thread is not None
        assert reader._thread.is_alive()

        reader.stop()
        # Thread should have exited
        assert not reader._thread.is_alive()

    @patch("brasa.core.serial.error")
    @patch("brasa.core.serial.pyserial.Serial")
    def test_serial_exception_logged_not_crash(
        self, mock_serial_cls: MagicMock, mock_error: MagicMock
    ) -> None:
        """SerialException during read is caught and logged."""
        mock_conn = MagicMock()
        mock_conn.is_open = True

        call_count = 0

        def _readline() -> bytes:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise pyserial.SerialException("device disconnected")
            time.sleep(0.05)
            return b""

        mock_conn.readline.side_effect = _readline
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader("/dev/ttyUSB0")
        reader.start_background()
        time.sleep(0.3)
        reader.stop()

        # Error should have been logged
        mock_error.assert_called()
        assert "serial read error" in mock_error.call_args[0][0]

    @patch("brasa.core.serial.pyserial.Serial")
    def test_start_background_creates_daemon_thread(self, mock_serial_cls: MagicMock) -> None:
        """start_background() starts a daemon thread."""
        mock_conn = _make_mock_serial([])
        mock_conn.readline.side_effect = lambda: (time.sleep(0.05) or b"")
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader("/dev/ttyUSB0")
        reader.start_background()

        assert reader._thread is not None
        assert reader._thread.daemon is True
        assert reader._thread.is_alive()

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
        time.sleep(0.2)

        mock_error.assert_called()
        assert "could not open" in mock_error.call_args[0][0]
