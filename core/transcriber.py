"""
Transcription engine using faster-whisper.

Provides segment-level cancel control by iterating the segment generator
and checking a shared threading event between yields.
Progress is reported via a callback function for UI integration.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

from faster_whisper import WhisperModel

from utils.logger import get_logger

logger = get_logger(__name__)


class TranscriptionState(Enum):
    """Possible states of a transcription job."""
    IDLE = auto()
    LOADING_MODEL = auto()
    TRANSCRIBING = auto()
    CANCELLING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


# Available model sizes (smallest -> largest)
MODEL_SIZES: list[str] = [
    "tiny", "tiny.en",
    "base", "base.en",
    "small", "small.en",
    "medium", "medium.en",
    "large-v1", "large-v2", "large-v3",
    "distil-large-v3",
]

DEFAULT_MODEL: str = "large-v3"


@dataclass
class TranscriptionProgress:
    """Progress data passed to the UI callback."""
    state: TranscriptionState
    segments_done: int = 0
    current_text: str = ""
    full_text: str = ""
    elapsed_seconds: float = 0.0
    audio_duration: float = 0.0
    audio_processed: float = 0.0
    error_message: str = ""


@dataclass
class TranscriptionResult:
    """Final result of a transcription job."""
    success: bool
    text: str = ""
    segments_count: int = 0
    audio_duration: float = 0.0
    processing_time: float = 0.0
    language: str = ""
    language_probability: float = 0.0
    error_message: str = ""


class Transcriber:
    """
    Audio transcription engine with threading controls.

    Usage:
        transcriber = Transcriber(progress_callback=my_callback)
        transcriber.start("lecture.mp3", model_size="large-v3")
        transcriber.cancel()
    """

    def __init__(
        self,
        progress_callback: Optional[Callable[[TranscriptionProgress], None]] = None,
        completion_callback: Optional[Callable[[TranscriptionResult], None]] = None,
    ) -> None:
        self._progress_callback = progress_callback
        self._completion_callback = completion_callback

        self._model: Optional[WhisperModel] = None
        self._current_model_size: Optional[str] = None

        # Threading controls
        self._state = TranscriptionState.IDLE
        self._state_lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    @property
    def state(self) -> TranscriptionState:
        """Current transcription state (thread-safe read)."""
        with self._state_lock:
            return self._state

    @state.setter
    def state(self, new_state: TranscriptionState) -> None:
        with self._state_lock:
            self._state = new_state

    @property
    def is_busy(self) -> bool:
        """True if a transcription is in progress."""
        return self.state in {
            TranscriptionState.LOADING_MODEL,
            TranscriptionState.TRANSCRIBING,
            TranscriptionState.CANCELLING,
        }

    def _detect_device(self) -> tuple[str, str]:
        """
        Detect the best available compute device.

        Returns:
            Tuple of (device, compute_type) for faster-whisper.
        """
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                logger.info("CUDA available: %s (%.1f GB VRAM)", gpu_name, vram_gb)
                return "cuda", "float16"
        except ImportError:
            logger.debug("PyTorch not installed -- skipping CUDA detection.")
        except Exception as e:
            logger.warning("CUDA detection failed: %s", e)

        logger.info("Using CPU for transcription.")
        return "cpu", "int8"

    def _load_model(self, model_size: str) -> None:
        """
        Load or reuse a faster-whisper model.

        Only reloads if the requested model differs from the cached one.
        """
        if self._model is not None and self._current_model_size == model_size:
            logger.info("Reusing cached model: %s", model_size)
            return

        device, compute_type = self._detect_device()

        logger.info(
            "Loading model '%s' on %s (compute: %s)...",
            model_size, device, compute_type,
        )

        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=4,
        )
        self._current_model_size = model_size
        logger.info("Model '%s' loaded successfully.", model_size)

    def _report_progress(self, progress: TranscriptionProgress) -> None:
        """Safely invoke the progress callback."""
        if self._progress_callback:
            try:
                self._progress_callback(progress)
            except Exception as e:
                logger.error("Progress callback error: %s", e)

    def _report_completion(self, result: TranscriptionResult) -> None:
        """Safely invoke the completion callback."""
        if self._completion_callback:
            try:
                self._completion_callback(result)
            except Exception as e:
                logger.error("Completion callback error: %s", e)

    def _transcribe_worker(self, file_path: Path, model_size: str) -> None:
        """
        Worker method that runs in a background thread.

        Iterates through segments from faster-whisper, checking cancel
        event between each segment for responsive user control.
        """
        start_time = time.monotonic()
        collected_segments: list[str] = []
        segments_done = 0
        audio_duration = 0.0
        detected_language = ""
        language_probability = 0.0

        try:
            # --- Load model ---
            self.state = TranscriptionState.LOADING_MODEL
            self._report_progress(TranscriptionProgress(
                state=TranscriptionState.LOADING_MODEL,
            ))

            self._load_model(model_size)

            # Check for cancel during model load
            if self._cancel_event.is_set():
                self.state = TranscriptionState.CANCELLED
                self._report_completion(TranscriptionResult(
                    success=False,
                    error_message="Cancelled during model loading.",
                ))
                return

            # --- Begin transcription ---
            self.state = TranscriptionState.TRANSCRIBING
            logger.info("Starting transcription: %s", file_path.name)

            segments_generator, info = self._model.transcribe(
                str(file_path),
                beam_size=5,
                language=None,        # Auto-detect
                vad_filter=True,      # Voice activity detection -- skips silence
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                ),
            )

            audio_duration = info.duration
            detected_language = info.language
            language_probability = info.language_probability

            logger.info(
                "Audio duration: %.1fs | Language: %s (%.1f%% confidence)",
                audio_duration, detected_language, language_probability * 100,
            )

            # --- Iterate segments ---
            for segment in segments_generator:
                # Cancel check
                if self._cancel_event.is_set():
                    logger.info("Transcription cancelled by user at segment %d.", segments_done)
                    self.state = TranscriptionState.CANCELLED
                    self._report_completion(TranscriptionResult(
                        success=False,
                        text="\n".join(collected_segments),
                        segments_count=segments_done,
                        audio_duration=audio_duration,
                        processing_time=time.monotonic() - start_time,
                        language=detected_language,
                        language_probability=language_probability,
                        error_message="Cancelled by user.",
                    ))
                    return

                # Collect segment text
                segment_text = segment.text.strip()
                if segment_text:
                    collected_segments.append(segment_text)

                segments_done += 1

                # Report progress
                self._report_progress(TranscriptionProgress(
                    state=TranscriptionState.TRANSCRIBING,
                    segments_done=segments_done,
                    current_text=segment_text,
                    full_text="\n".join(collected_segments),
                    elapsed_seconds=time.monotonic() - start_time,
                    audio_duration=audio_duration,
                    audio_processed=segment.end,
                ))

            # --- Completed successfully ---
            elapsed = time.monotonic() - start_time
            final_text = "\n".join(collected_segments)
            self.state = TranscriptionState.COMPLETED

            logger.info(
                "Transcription complete: %d segments in %.1fs (%.1fx realtime)",
                segments_done, elapsed,
                audio_duration / elapsed if elapsed > 0 else 0,
            )

            self._report_completion(TranscriptionResult(
                success=True,
                text=final_text,
                segments_count=segments_done,
                audio_duration=audio_duration,
                processing_time=elapsed,
                language=detected_language,
                language_probability=language_probability,
            ))

        except Exception as e:
            elapsed = time.monotonic() - start_time
            self.state = TranscriptionState.FAILED
            error_msg = f"{type(e).__name__}: {e}"
            logger.exception("Transcription failed: %s", error_msg)

            self._report_completion(TranscriptionResult(
                success=False,
                text="\n".join(collected_segments),
                segments_count=segments_done,
                audio_duration=audio_duration,
                processing_time=elapsed,
                language=detected_language,
                language_probability=language_probability,
                error_message=error_msg,
            ))

    def start(self, file_path: str | Path, model_size: str = DEFAULT_MODEL) -> None:
        """
        Begin transcription in a background thread.

        Args:
            file_path: Path to the audio file.
            model_size: Whisper model size to use.

        Raises:
            RuntimeError: If a transcription is already in progress.
            ValueError: If the model size is invalid.
        """
        if self.is_busy:
            raise RuntimeError("A transcription is already in progress.")

        if model_size not in MODEL_SIZES:
            raise ValueError(
                f"Invalid model '{model_size}'. Choose from: {', '.join(MODEL_SIZES)}"
            )

        path = Path(file_path).resolve()

        # Reset cancel flag
        self._cancel_event.clear()

        self._worker_thread = threading.Thread(
            target=self._transcribe_worker,
            args=(path, model_size),
            name="TranscriberWorker",
            daemon=True,
        )
        self._worker_thread.start()
        logger.info("Transcription thread started for: %s", path.name)

    def cancel(self) -> None:
        """Cancel the current transcription."""
        if self.is_busy:
            self.state = TranscriptionState.CANCELLING
            self._cancel_event.set()
            logger.info("Cancel requested.")

    def cleanup(self) -> None:
        """
        Release model resources.

        Does NOT block waiting for the worker thread -- the thread is
        daemonic and will be killed when the process exits.
        """
        if self._worker_thread and self._worker_thread.is_alive():
            self.cancel()
            # Don't join -- thread is daemon, it dies with the process.
            # Joining here blocks the UI and prevents the window from closing.

        self._model = None
        self._current_model_size = None
        logger.info("Transcriber resources cleaned up.")