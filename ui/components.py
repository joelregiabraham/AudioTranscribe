"""
Reusable UI components built on CustomTkinter.

Provides styled widgets that conform to the application theme
for consistent look-and-feel across the interface.
"""

from __future__ import annotations

import customtkinter as ctk

from ui.theme import COLORS, FONTS, SPACING


class StatusBadge(ctk.CTkLabel):
    """A small colored label that indicates current status."""

    _STATUS_COLORS = {
        "idle": COLORS.text_muted,
        "loading": COLORS.warning,
        "transcribing": COLORS.accent,
        "completed": COLORS.success,
        "failed": COLORS.error,
        "cancelled": COLORS.text_muted,
    }

    def __init__(self, master: ctk.CTkBaseClass, **kwargs) -> None:
        super().__init__(
            master,
            text="● Idle",
            font=(FONTS.family, FONTS.size_small, "bold"),
            text_color=COLORS.text_muted,
            **kwargs,
        )

    def set_status(self, status: str, label: str | None = None) -> None:
        """Update the badge status and optional label text."""
        color = self._STATUS_COLORS.get(status.lower(), COLORS.text_muted)
        display = label if label else status.capitalize()
        self.configure(text=f"● {display}", text_color=color)


class FileInfoCard(ctk.CTkFrame):
    """
    Card that displays selected file information.

    Shows filename, size, and format in a compact card layout.
    """

    def __init__(self, master: ctk.CTkBaseClass, **kwargs) -> None:
        super().__init__(
            master,
            fg_color=COLORS.bg_card,
            corner_radius=10,
            border_width=1,
            border_color=COLORS.border,
            **kwargs,
        )

        self._filename_label = ctk.CTkLabel(
            self,
            text="No file selected",
            font=(FONTS.family, FONTS.size_normal, "bold"),
            text_color=COLORS.text_primary,
            anchor="w",
        )
        self._filename_label.pack(
            padx=SPACING.lg, pady=(SPACING.md, SPACING.xs), fill="x",
        )

        self._details_label = ctk.CTkLabel(
            self,
            text="Select an audio file to begin",
            font=(FONTS.family, FONTS.size_small),
            text_color=COLORS.text_secondary,
            anchor="w",
        )
        self._details_label.pack(
            padx=SPACING.lg, pady=(0, SPACING.md), fill="x",
        )

    def set_file(self, filename: str, size: str, fmt: str) -> None:
        """Update the card with file information."""
        self._filename_label.configure(text=filename)
        self._details_label.configure(text=f"{size}  •  {fmt.upper()}")
        self.configure(border_color=COLORS.accent)

    def clear(self) -> None:
        """Reset the card to its empty state."""
        self._filename_label.configure(text="No file selected")
        self._details_label.configure(text="Select an audio file to begin")
        self.configure(border_color=COLORS.border)


class ProgressSection(ctk.CTkFrame):
    """
    Progress display with a bar, percentage, and time information.
    """

    def __init__(self, master: ctk.CTkBaseClass, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        # Top row: percentage + time
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, SPACING.xs))

        self._percent_label = ctk.CTkLabel(
            top_row,
            text="0%",
            font=(FONTS.family, FONTS.size_normal, "bold"),
            text_color=COLORS.accent,
        )
        self._percent_label.pack(side="left")

        self._time_label = ctk.CTkLabel(
            top_row,
            text="",
            font=(FONTS.family, FONTS.size_small),
            text_color=COLORS.text_secondary,
        )
        self._time_label.pack(side="right")

        # Progress bar
        self._progress_bar = ctk.CTkProgressBar(
            self,
            height=8,
            corner_radius=4,
            fg_color=COLORS.progress_bg,
            progress_color=COLORS.progress_fill,
        )
        self._progress_bar.pack(fill="x", pady=(0, SPACING.xs))
        self._progress_bar.set(0)

        # Segments info
        self._segments_label = ctk.CTkLabel(
            self,
            text="",
            font=(FONTS.family, FONTS.size_small),
            text_color=COLORS.text_muted,
        )
        self._segments_label.pack(anchor="w")

    def update_progress(
        self,
        fraction: float,
        elapsed: float,
        segments: int,
        audio_processed: float = 0.0,
        audio_duration: float = 0.0,
    ) -> None:
        """Update all progress indicators."""
        fraction = max(0.0, min(1.0, fraction))
        self._progress_bar.set(fraction)
        self._percent_label.configure(text=f"{fraction * 100:.1f}%")

        # Time display
        elapsed_str = self._format_time(elapsed)
        if fraction > 0.01:
            estimated_total = elapsed / fraction
            remaining = max(0, estimated_total - elapsed)
            remaining_str = self._format_time(remaining)
            self._time_label.configure(
                text=f"{elapsed_str} elapsed  •  ~{remaining_str} remaining"
            )
        else:
            self._time_label.configure(text=f"{elapsed_str} elapsed")

        # Segments info
        if audio_duration > 0:
            processed_str = self._format_time(audio_processed)
            duration_str = self._format_time(audio_duration)
            self._segments_label.configure(
                text=f"{segments} segments  •  {processed_str} / {duration_str} processed"
            )
        else:
            self._segments_label.configure(text=f"{segments} segments processed")

    def reset(self) -> None:
        """Reset to initial state."""
        self._progress_bar.set(0)
        self._percent_label.configure(text="0%")
        self._time_label.configure(text="")
        self._segments_label.configure(text="")

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds to a human-readable string."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        if minutes < 60:
            return f"{minutes}m {secs:02d}s"
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins:02d}m"