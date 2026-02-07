"""
Main application window.

Orchestrates the UI layout, user interactions, and communication with
the transcription engine via callbacks and CustomTkinter's thread-safe
`after()` scheduling.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from tkinter import filedialog, END as TK_END
from typing import Optional

import customtkinter as ctk

from core.file_handler import (
    FILETYPES,
    generate_output_path,
    get_file_size_display,
    save_transcript,
    validate_audio_file,
)
from core.transcriber import (
    DEFAULT_MODEL,
    MODEL_SIZES,
    TranscriptionProgress,
    TranscriptionResult,
    TranscriptionState,
    Transcriber,
)
from ui.components import FileInfoCard, ProgressSection, StatusBadge
from ui.theme import COLORS, FONTS, SPACING
from utils.logger import get_logger

logger = get_logger(__name__)

# Window geometry
_WINDOW_WIDTH = 900
_WINDOW_HEIGHT = 740
_MIN_WIDTH = 750
_MIN_HEIGHT = 650


class TranscriberApp(ctk.CTk):
    """
    Main application window for the Audio Transcriber.

    Manages layout, user interactions, and delegates transcription
    to the Transcriber engine running in a background thread.
    """

    def __init__(self) -> None:
        super().__init__()

        # -- Window setup --
        self.title("Audio Transcriber")
        self.geometry(f"{_WINDOW_WIDTH}x{_WINDOW_HEIGHT}")
        self.minsize(_MIN_WIDTH, _MIN_HEIGHT)
        self.configure(fg_color=COLORS.bg_primary)

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - _WINDOW_WIDTH) // 2
        y = (self.winfo_screenheight() - _WINDOW_HEIGHT) // 2
        self.geometry(f"+{x}+{y}")

        # -- State --
        self._selected_file: Optional[Path] = None
        self._last_result: Optional[TranscriptionResult] = None
        self._closing = False

        # Pending UI updates from worker thread (thread-safe queue via list+lock)
        self._pending_updates: list[TranscriptionProgress | TranscriptionResult] = []
        self._update_lock = threading.Lock()

        # -- Transcriber engine --
        self._transcriber = Transcriber(
            progress_callback=self._on_progress,
            completion_callback=self._on_completion,
        )

        # -- Build UI --
        self._build_header()
        self._build_file_section()
        self._build_options_section()
        self._build_controls_section()
        self._build_progress_section()
        self._build_transcript_section()

        # -- Start UI polling loop --
        self._poll_updates()

        # -- Clean shutdown --
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ #
    #  UI Construction
    # ------------------------------------------------------------------ #

    def _build_header(self) -> None:
        """Title bar and status badge."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=SPACING.xl, pady=(SPACING.xl, SPACING.lg))

        title = ctk.CTkLabel(
            header,
            text="Audio Transcriber",
            font=(FONTS.family, FONTS.size_title, "bold"),
            text_color=COLORS.text_primary,
        )
        title.pack(side="left")

        self._status_badge = StatusBadge(header)
        self._status_badge.pack(side="right")

    def _build_file_section(self) -> None:
        """File selection area with browse button and info card."""
        section = ctk.CTkFrame(self, fg_color="transparent")
        section.pack(fill="x", padx=SPACING.xl, pady=(0, SPACING.md))

        # Browse button row
        btn_row = ctk.CTkFrame(section, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, SPACING.sm))

        self._browse_btn = ctk.CTkButton(
            btn_row,
            text="Browse Audio File",
            font=(FONTS.family, FONTS.size_normal, "bold"),
            fg_color=COLORS.accent,
            hover_color=COLORS.accent_hover,
            text_color=COLORS.text_on_accent,
            height=40,
            corner_radius=8,
            command=self._browse_file,
        )
        self._browse_btn.pack(side="left")

        self._clear_btn = ctk.CTkButton(
            btn_row,
            text="Clear",
            font=(FONTS.family, FONTS.size_small),
            fg_color=COLORS.btn_secondary,
            hover_color=COLORS.btn_secondary_hover,
            text_color=COLORS.text_primary,
            width=70,
            height=40,
            corner_radius=8,
            command=self._clear_selection,
        )
        self._clear_btn.pack(side="left", padx=(SPACING.sm, 0))

        # File info card
        self._file_card = FileInfoCard(section)
        self._file_card.pack(fill="x")

    def _build_options_section(self) -> None:
        """Model selection dropdown."""
        section = ctk.CTkFrame(self, fg_color="transparent")
        section.pack(fill="x", padx=SPACING.xl, pady=(0, SPACING.md))

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x")

        label = ctk.CTkLabel(
            row,
            text="Model",
            font=(FONTS.family, FONTS.size_normal),
            text_color=COLORS.text_secondary,
        )
        label.pack(side="left", padx=(0, SPACING.sm))

        self._model_var = ctk.StringVar(value=DEFAULT_MODEL)
        self._model_dropdown = ctk.CTkOptionMenu(
            row,
            variable=self._model_var,
            values=MODEL_SIZES,
            font=(FONTS.family, FONTS.size_small),
            dropdown_font=(FONTS.family, FONTS.size_small),
            fg_color=COLORS.bg_card,
            button_color=COLORS.accent_dark,
            button_hover_color=COLORS.accent,
            dropdown_fg_color=COLORS.bg_card,
            dropdown_hover_color=COLORS.bg_hover,
            text_color=COLORS.text_primary,
            dropdown_text_color=COLORS.text_primary,
            width=180,
            height=36,
            corner_radius=8,
        )
        self._model_dropdown.pack(side="left")

        # GPU/CPU indicator
        self._device_label = ctk.CTkLabel(
            row,
            text="",
            font=(FONTS.family, FONTS.size_small),
            text_color=COLORS.text_muted,
        )
        self._device_label.pack(side="right")
        self._detect_and_show_device()

    def _build_controls_section(self) -> None:
        """Start, Cancel, and Save buttons."""
        section = ctk.CTkFrame(self, fg_color="transparent")
        section.pack(fill="x", padx=SPACING.xl, pady=(0, SPACING.md))

        self._start_btn = ctk.CTkButton(
            section,
            text="\u25b6  Start Transcription",
            font=(FONTS.family, FONTS.size_normal, "bold"),
            fg_color=COLORS.success,
            hover_color="#81c784",
            text_color=COLORS.text_on_accent,
            height=44,
            corner_radius=8,
            command=self._start_transcription,
        )
        self._start_btn.pack(side="left", padx=(0, SPACING.sm))

        self._cancel_btn = ctk.CTkButton(
            section,
            text="\u2715  Cancel",
            font=(FONTS.family, FONTS.size_normal),
            fg_color=COLORS.btn_danger,
            hover_color=COLORS.btn_danger_hover,
            text_color=COLORS.text_primary,
            height=44,
            corner_radius=8,
            state="disabled",
            command=self._cancel_transcription,
        )
        self._cancel_btn.pack(side="left")

        self._save_btn = ctk.CTkButton(
            section,
            text="\U0001f4be  Save Transcript",
            font=(FONTS.family, FONTS.size_normal, "bold"),
            fg_color=COLORS.accent,
            hover_color=COLORS.accent_hover,
            text_color=COLORS.text_on_accent,
            height=44,
            corner_radius=8,
            state="disabled",
            command=self._save_transcript,
        )
        self._save_btn.pack(side="right")

    def _build_progress_section(self) -> None:
        """Progress bar and stats."""
        self._progress = ProgressSection(self)
        self._progress.pack(fill="x", padx=SPACING.xl, pady=(0, SPACING.md))

    def _build_transcript_section(self) -> None:
        """Live transcript text area."""
        section = ctk.CTkFrame(self, fg_color="transparent")
        section.pack(fill="both", expand=True, padx=SPACING.xl, pady=(0, SPACING.xl))

        label = ctk.CTkLabel(
            section,
            text="Transcript",
            font=(FONTS.family, FONTS.size_normal, "bold"),
            text_color=COLORS.text_secondary,
        )
        label.pack(anchor="w", pady=(0, SPACING.xs))

        self._transcript_box = ctk.CTkTextbox(
            section,
            font=(FONTS.family_mono, FONTS.size_small),
            fg_color=COLORS.bg_input,
            text_color=COLORS.text_primary,
            border_width=1,
            border_color=COLORS.border,
            corner_radius=8,
            wrap="word",
            activate_scrollbars=True,
        )
        self._transcript_box.pack(fill="both", expand=True)

    # ------------------------------------------------------------------ #
    #  Actions
    # ------------------------------------------------------------------ #

    def _browse_file(self) -> None:
        """Open a file dialog and validate the selected audio file."""
        path = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=FILETYPES,
        )
        if not path:
            return

        try:
            validated = validate_audio_file(path)
            self._selected_file = validated
            size_str = get_file_size_display(validated)
            fmt = validated.suffix.lstrip(".")
            self._file_card.set_file(validated.name, size_str, fmt)
            self._start_btn.configure(state="normal")
            logger.info("File selected: %s", validated.name)
        except (FileNotFoundError, ValueError, PermissionError) as e:
            self._show_error(str(e))
            logger.warning("File validation failed: %s", e)

    def _clear_selection(self) -> None:
        """Clear the selected file and reset related UI."""
        self._selected_file = None
        self._file_card.clear()
        self._start_btn.configure(state="normal")

    def _start_transcription(self) -> None:
        """Kick off a new transcription job."""
        if self._selected_file is None:
            self._show_error("Please select an audio file first.")
            return

        if self._transcriber.is_busy:
            return

        # Reset UI
        self._transcript_box.delete("1.0", TK_END)
        self._progress.reset()
        self._last_result = None

        # Update button states
        self._start_btn.configure(state="disabled")
        self._browse_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._save_btn.configure(state="disabled")
        self._model_dropdown.configure(state="disabled")

        model = self._model_var.get()
        logger.info("Starting transcription: file=%s, model=%s", self._selected_file.name, model)

        try:
            self._transcriber.start(self._selected_file, model_size=model)
        except (RuntimeError, ValueError) as e:
            self._show_error(str(e))
            self._reset_controls()

    def _cancel_transcription(self) -> None:
        """Cancel the running transcription."""
        self._transcriber.cancel()
        self._cancel_btn.configure(state="disabled")

    def _save_transcript(self) -> None:
        """Save the transcript text to a .txt file."""
        text = self._transcript_box.get("1.0", TK_END).strip()
        if not text:
            self._show_error("No transcript text to save.")
            return

        # Suggest default path
        default_path = ""
        if self._selected_file:
            default_path = str(generate_output_path(self._selected_file))

        save_path = filedialog.asksaveasfilename(
            title="Save Transcript",
            defaultextension=".txt",
            initialfile=Path(default_path).name if default_path else "transcript.txt",
            initialdir=str(self._selected_file.parent) if self._selected_file else "",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if not save_path:
            return

        try:
            saved = save_transcript(text, save_path)
            self._status_badge.set_status("completed", f"Saved: {saved.name}")
            logger.info("Transcript saved to: %s", saved)
        except (ValueError, OSError) as e:
            self._show_error(f"Failed to save: {e}")

    # ------------------------------------------------------------------ #
    #  Thread-safe callback system
    # ------------------------------------------------------------------ #

    def _on_progress(self, progress: TranscriptionProgress) -> None:
        """
        Called by the transcription worker thread.

        Queues the update for the main thread to process via polling.
        """
        with self._update_lock:
            self._pending_updates.append(progress)

    def _on_completion(self, result: TranscriptionResult) -> None:
        """
        Called by the transcription worker thread on completion/failure/cancel.

        Queues the result for the main thread.
        """
        with self._update_lock:
            self._pending_updates.append(result)

    def _poll_updates(self) -> None:
        """
        Main-thread polling loop.

        Runs every 100ms, processes any queued updates from the worker thread.
        This avoids direct cross-thread UI manipulation.
        """
        if self._closing:
            return

        updates: list[TranscriptionProgress | TranscriptionResult] = []

        with self._update_lock:
            updates = self._pending_updates.copy()
            self._pending_updates.clear()

        for update in updates:
            if isinstance(update, TranscriptionProgress):
                self._apply_progress(update)
            elif isinstance(update, TranscriptionResult):
                self._apply_result(update)

        self.after(100, self._poll_updates)

    def _apply_progress(self, p: TranscriptionProgress) -> None:
        """Apply a progress update to the UI (main thread only)."""
        # Status badge
        state_labels = {
            TranscriptionState.LOADING_MODEL: ("loading", "Loading model..."),
            TranscriptionState.TRANSCRIBING: ("transcribing", "Transcribing..."),
        }
        if p.state in state_labels:
            status, label = state_labels[p.state]
            self._status_badge.set_status(status, label)

        # Progress bar
        if p.audio_duration > 0:
            fraction = p.audio_processed / p.audio_duration
        else:
            fraction = 0.0

        self._progress.update_progress(
            fraction=fraction,
            elapsed=p.elapsed_seconds,
            segments=p.segments_done,
            audio_processed=p.audio_processed,
            audio_duration=p.audio_duration,
        )

        # Live transcript
        if p.full_text:
            self._transcript_box.delete("1.0", TK_END)
            self._transcript_box.insert("1.0", p.full_text)
            self._transcript_box.see(TK_END)

    def _apply_result(self, r: TranscriptionResult) -> None:
        """Apply a final result to the UI (main thread only)."""
        self._last_result = r

        if r.success:
            self._status_badge.set_status("completed", "Completed")
            self._progress.update_progress(
                fraction=1.0,
                elapsed=r.processing_time,
                segments=r.segments_count,
                audio_processed=r.audio_duration,
                audio_duration=r.audio_duration,
            )

            # Final transcript
            if r.text:
                self._transcript_box.delete("1.0", TK_END)
                self._transcript_box.insert("1.0", r.text)
                self._transcript_box.see(TK_END)

            speed = r.audio_duration / r.processing_time if r.processing_time > 0 else 0
            logger.info(
                "UI updated: complete -- %d segments, %.1fx realtime, lang=%s",
                r.segments_count, speed, r.language,
            )
        elif "Cancelled" in (r.error_message or ""):
            self._status_badge.set_status("cancelled", "Cancelled")
        else:
            self._status_badge.set_status("failed", "Failed")
            self._show_error(r.error_message or "Unknown error occurred.")

        self._reset_controls()

        # Enable save if there's any text
        text = self._transcript_box.get("1.0", TK_END).strip()
        if text:
            self._save_btn.configure(state="normal")

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _reset_controls(self) -> None:
        """Re-enable controls after transcription ends."""
        self._start_btn.configure(state="normal")
        self._browse_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        self._model_dropdown.configure(state="normal")

    def _detect_and_show_device(self) -> None:
        """Detect GPU/CPU and update the device label."""
        try:
            import torch
            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                self._device_label.configure(
                    text=f"\U0001f7e2  GPU: {name}",
                    text_color=COLORS.success,
                )
                return
        except ImportError:
            pass
        except Exception:
            pass

        self._device_label.configure(
            text="\u26aa  CPU mode",
            text_color=COLORS.text_muted,
        )

    def _show_error(self, message: str) -> None:
        """Display an error dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Error")
        dialog.geometry("450x180")
        dialog.configure(fg_color=COLORS.bg_secondary)
        dialog.transient(self)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 450) // 2
        y = self.winfo_y() + (self.winfo_height() - 180) // 2
        dialog.geometry(f"+{x}+{y}")

        icon = ctk.CTkLabel(
            dialog,
            text="\u26a0",
            font=(FONTS.family, 28),
            text_color=COLORS.error,
        )
        icon.pack(pady=(SPACING.lg, SPACING.xs))

        msg = ctk.CTkLabel(
            dialog,
            text=message,
            font=(FONTS.family, FONTS.size_small),
            text_color=COLORS.text_primary,
            wraplength=400,
        )
        msg.pack(padx=SPACING.lg, pady=(0, SPACING.md))

        ok_btn = ctk.CTkButton(
            dialog,
            text="OK",
            width=80,
            fg_color=COLORS.accent,
            hover_color=COLORS.accent_hover,
            text_color=COLORS.text_on_accent,
            command=dialog.destroy,
        )
        ok_btn.pack(pady=(0, SPACING.lg))

    def _on_close(self) -> None:
        """
        Clean shutdown: signal cancel and destroy immediately.

        The worker thread is daemonic, so it will be killed when the
        process exits. We do NOT join/wait for it -- that's what was
        causing the close button to hang.
        """
        logger.info("Application closing...")
        self._closing = True
        self._transcriber.cleanup()
        self.destroy()
        # Force-exit the process in case daemon threads hold resources
        os._exit(0)