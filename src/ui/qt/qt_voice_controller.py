import logging
import threading
from typing import Optional, Callable

from PyQt5.QtCore import QTimer, Qt, QObject, pyqtSignal

from ..protocols import MovementControllerProtocol
from ..robot_actions import invoke_robot_action
from ..voice.command_parser import parse_command, ParsedCommand
from ..voice.stt_provider import STTProvider

logger = logging.getLogger(__name__)

# Audio capture settings
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024  # frames per buffer
FORMAT_WIDTH = 2  # 16-bit = 2 bytes


class _VoiceSignals(QObject):
    """Qt signals for cross-thread communication from STT background thread."""
    status_update = pyqtSignal(str)
    command_ready = pyqtSignal(object)  # ParsedCommand


class VoiceController(MovementControllerProtocol):
    """Push-to-talk voice controller using local STT for robot commands."""

    def __init__(self, robot, stt_provider: STTProvider,
                 status_callback: Optional[Callable[[str], None]] = None):
        super().__init__(robot)
        self._stt = stt_provider
        self._status_callback = status_callback

        # Qt signals for thread-safe main-thread dispatch
        self._signals = _VoiceSignals()
        self._signals.status_update.connect(self._set_status)
        self._signals.command_ready.connect(self._execute_command)

        # Audio capture state
        self._pyaudio = None
        self._stream = None
        self._recording = False
        self._audio_frames: list[bytes] = []
        self._audio_lock = threading.Lock()
        self._record_thread: Optional[threading.Thread] = None

        # Timed movement state
        self._move_timer: Optional[QTimer] = None
        self._move_stop_timer: Optional[QTimer] = None
        self._current_move = (0.0, 0.0, 0.0)

        # Toggle state for shared action utility
        self._flash_state = {'value': 0.0}
        self._led_state = {'value': 0}
        self._lidar_state = {'value': True}

    def setup(self):
        try:
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()
        except Exception:
            logger.exception("Failed to initialize PyAudio")

    def cleanup(self):
        self.stop_recording()
        self._cancel_timed_move()
        if self._pyaudio:
            try:
                self._pyaudio.terminate()
            except Exception:
                pass
            self._pyaudio = None

    def start_recording(self):
        """Begin capturing audio (push-to-talk press)."""
        if self._recording or self._pyaudio is None:
            return
        self._recording = True
        self._audio_frames = []
        self._set_status("Listening...")

        try:
            self._stream = self._pyaudio.open(
                format=self._pyaudio.get_format_from_width(FORMAT_WIDTH),
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )
        except Exception:
            logger.exception("Failed to open audio stream")
            self._recording = False
            self._set_status("Mic error")
            return

        self._record_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._record_thread.start()

    def stop_recording(self):
        """Stop capturing audio and process (push-to-talk release)."""
        if not self._recording:
            return
        self._recording = False

        # Wait for capture thread to finish
        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join(timeout=1.0)
        self._record_thread = None

        # Close stream
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._audio_lock:
            frames = list(self._audio_frames)
            self._audio_frames = []

        if not frames:
            self._set_status("")
            return

        audio_data = b"".join(frames)
        self._set_status("Processing...")

        # Transcribe in background thread to avoid blocking UI
        thread = threading.Thread(
            target=self._transcribe_and_execute,
            args=(audio_data,),
            daemon=True,
        )
        thread.start()

    def _capture_loop(self):
        """Background thread: read audio chunks while recording."""
        while self._recording and self._stream:
            try:
                data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                with self._audio_lock:
                    self._audio_frames.append(data)
            except Exception:
                break

    def _transcribe_and_execute(self, audio_data: bytes):
        """Background thread: transcribe audio, then dispatch command on main thread via signal."""
        # Show loading status if this is the first transcription (model download may take a while)
        if not hasattr(self._stt, '_model') or self._stt._model is None:
            self._signals.status_update.emit("Loading model (first use)...")

        try:
            text = self._stt.transcribe(audio_data, SAMPLE_RATE)
        except Exception as e:
            logger.exception("STT transcription error")
            self._signals.status_update.emit(f"STT error: {e}")
            return

        if not text:
            self._signals.status_update.emit("(nothing recognized)")
            return

        command = parse_command(text)
        self._signals.command_ready.emit(command)

    def _execute_command(self, cmd: ParsedCommand):
        """Execute a parsed command on the main (Qt) thread."""
        display = cmd.raw_text or ""

        if cmd.is_stop:
            self._cancel_timed_move()
            if hasattr(self.robot, "stop_move"):
                self.robot.stop_move()
            if hasattr(self.robot, "move"):
                self.robot.move(0, 0, 0)
            self._set_status(f'"{display}" -> Stop')
            return

        if cmd.timed_move is not None:
            tm = cmd.timed_move
            self._start_timed_move(tm.x, tm.y, tm.z, tm.duration)
            self._set_status(f'"{display}" -> Move {tm.duration:.1f}s')
            return

        if cmd.action is not None:
            invoke_robot_action(
                self.robot, cmd.action,
                flash_state=self._flash_state,
                led_state=self._led_state,
                lidar_state=self._lidar_state,
            )
            self._set_status(f'"{display}" -> {cmd.action.name}')
            return

        self._set_status(f'"{display}" (unknown command)')

    def _start_timed_move(self, x: float, y: float, z: float, duration: float):
        """Start a timed movement: send move commands at 100ms intervals, stop after duration."""
        self._cancel_timed_move()
        self._current_move = (x, y, z)

        # Tick timer: send move every 100ms
        self._move_timer = QTimer()
        self._move_timer.timeout.connect(self._on_move_tick)
        self._move_timer.start(100)

        # Stop timer: cancel after duration
        self._move_stop_timer = QTimer()
        self._move_stop_timer.setSingleShot(True)
        self._move_stop_timer.timeout.connect(self._on_timed_move_end)
        self._move_stop_timer.start(int(duration * 1000))

    def _on_move_tick(self):
        x, y, z = self._current_move
        if self.robot.is_connected and hasattr(self.robot, "move"):
            self.robot.move(x, y, z)

    def _on_timed_move_end(self):
        self._cancel_timed_move()
        if self.robot.is_connected and hasattr(self.robot, "move"):
            self.robot.move(0, 0, 0)
        self._set_status("Move complete")

    def _cancel_timed_move(self):
        if self._move_timer:
            self._move_timer.stop()
            self._move_timer = None
        if self._move_stop_timer:
            self._move_stop_timer.stop()
            self._move_stop_timer = None
        self._current_move = (0.0, 0.0, 0.0)

    def _set_status(self, text: str):
        if self._status_callback:
            try:
                self._status_callback(text)
            except Exception:
                pass

    # Keyboard PTT: V key
    def handle_key_press(self, key):
        if key == Qt.Key_V:
            self.start_recording()
            return True
        return False

    def handle_key_release(self, key):
        if key == Qt.Key_V:
            self.stop_recording()
            return True
        return False
