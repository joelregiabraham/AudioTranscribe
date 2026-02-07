"""
Dark theme configuration for the transcriber UI.

Centralizes all colors, fonts, and spacing so the look-and-feel
can be adjusted in one place.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Colors:
    """Application color palette — dark theme."""

    # Backgrounds
    bg_primary: str = "#1a1a2e"
    bg_secondary: str = "#16213e"
    bg_card: str = "#1f2940"
    bg_input: str = "#0f1626"
    bg_hover: str = "#253354"

    # Accent
    accent: str = "#4fc3f7"
    accent_hover: str = "#81d4fa"
    accent_dark: str = "#0288d1"

    # Status
    success: str = "#66bb6a"
    warning: str = "#ffa726"
    error: str = "#ef5350"
    info: str = "#42a5f5"

    # Text
    text_primary: str = "#e8eaf6"
    text_secondary: str = "#9e9eb8"
    text_muted: str = "#6c6c8a"
    text_on_accent: str = "#0a0a1a"

    # Borders
    border: str = "#2a3a5c"
    border_focus: str = "#4fc3f7"

    # Progress bar
    progress_bg: str = "#1a2744"
    progress_fill: str = "#4fc3f7"

    # Buttons
    btn_danger: str = "#c62828"
    btn_danger_hover: str = "#e53935"
    btn_secondary: str = "#37474f"
    btn_secondary_hover: str = "#455a64"


@dataclass(frozen=True)
class Fonts:
    """Font configuration."""
    family: str = "Segoe UI"
    family_mono: str = "Cascadia Code"
    size_small: int = 11
    size_normal: int = 13
    size_large: int = 15
    size_title: int = 22
    size_subtitle: int = 16


@dataclass(frozen=True)
class Spacing:
    """Padding and margin constants."""
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


# Singleton instances
COLORS = Colors()
FONTS = Fonts()
SPACING = Spacing()
