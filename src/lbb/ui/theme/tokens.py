"""Design tokens for the Flanacom Tool UI.

Light theme tuned to the Flanacom brand: warm orange primary action,
clean off-white surfaces, near-black wordmark text. Token table mirrored
in `app.qss` — keep them in sync.
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
    # Surfaces — light off-white background, white cards, subtle elevated tones.
    BG = "#FAFAFA"
    SURFACE = "#FFFFFF"
    SURFACE_ELEVATED = "#FFFFFF"  # shadows do the lifting (QGraphicsDropShadowEffect)
    SURFACE_HOVER = "#F5F5F4"
    BORDER = "#E5E7EB"
    BORDER_STRONG = "#D1D5DB"

    # Text — black-ish (matches the Flanacom wordmark) at the top of the scale.
    TEXT = "#1A1A1A"
    TEXT_DIM = "#6B7280"
    TEXT_FAINT = "#9CA3AF"

    # Accent — Flanacom orange (the shopping-bag mark).
    ACCENT = "#F58A1F"
    ACCENT_HOVER = "#FFA947"
    ACCENT_PRESSED = "#D97706"
    ACCENT_DIM = "#FBBF77"
    ACCENT_TINT = "#FFF3E5"  # very faint peach for hover backgrounds

    # Status — high-contrast against the light surfaces.
    OK = "#10B981"
    WARN = "#F59E0B"
    ERROR = "#DC2626"

    # Layer-color references (mirrors core.palette indices for surfacing layer
    # info in the preview chip etc.). On a light bg, black represents cut
    # directly; engrave borrows the brand orange.
    LAYER_CUT = "#1A1A1A"
    LAYER_ENGRAVE = "#F58A1F"


class Radius:
    XS = 4
    SM = 6
    MD = 8
    LG = 12
    XL = 18


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
