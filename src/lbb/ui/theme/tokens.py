"""Design tokens for the LightBurn Bridge UI.

Refined minimalism — Linear / Things 3 / Raycast aesthetic. Dark by default
for laser-shop floor conditions; high-contrast statuses so state changes
are unmistakable through safety glasses.
"""


class Font:
    # Platform-native display + body. macOS picks SF Pro, Windows picks Segoe
    # UI Variable, Linux falls back to Inter. No web-fonts needed.
    SANS = (
        '"SF Pro Text", "SF Pro Display", "Segoe UI Variable Text", '
        '"Segoe UI", "Inter", "Helvetica Neue", sans-serif'
    )
    DISPLAY = (
        '"SF Pro Display", "Segoe UI Variable Display", '
        '"Segoe UI", "Inter", "Helvetica Neue", sans-serif'
    )
    MONO = '"SF Mono", "Cascadia Mono", "JetBrains Mono", "Menlo", "Consolas", monospace'


class Color:
    # Surfaces — graduated darkness; the active surface is brighter than its
    # container so cards feel "lifted" without explicit shadows.
    BG = "#0A0C12"
    SURFACE = "#11141C"
    SURFACE_ELEVATED = "#161A25"
    SURFACE_HOVER = "#1B2030"
    BORDER = "#222837"
    BORDER_STRONG = "#2D3447"

    # Text
    TEXT = "#E6E8EE"
    TEXT_DIM = "#8A92A6"
    TEXT_FAINT = "#5B6479"

    # Accent — cyan-leaning, kept singular so it always means "primary action"
    ACCENT = "#7DD3FC"
    ACCENT_HOVER = "#A5E0FB"
    ACCENT_PRESSED = "#5CC3F0"
    ACCENT_DIM = "#3FA0CC"

    # Status — high-contrast through safety-glass tints
    OK = "#A3E635"
    WARN = "#FBBF24"
    ERROR = "#FB7185"

    # Layer-color references (mirrors core.palette indices 0..2 for the UI
    # to use when surfacing layer info in the preview chip etc.)
    LAYER_CUT = "#FFFFFF"  # render black-on-dark as white for contrast
    LAYER_ENGRAVE = "#7DD3FC"


class Radius:
    XS = 4
    SM = 6
    MD = 10
    LG = 14
    XL = 22


class Space:
    XS = 4
    SM = 8
    MD = 16
    LG = 24
    XL = 32
    XXL = 48


class Duration:
    INSTANT_MS = 80  # press feedback
    QUICK_MS = 160  # hover transitions
    MEDIUM_MS = 240  # view transitions
