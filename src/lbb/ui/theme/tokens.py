"""Design tokens for the LightBurn Bridge UI.

Dark by default — laser-shop floors are dim and operators wear safety glasses.
High-contrast accent + status colours so state changes are readable through
tinted lenses.
"""


class Color:
    # Surfaces
    BG = "#0B0D12"
    SURFACE = "#141821"
    SURFACE_ALT = "#1B2030"
    BORDER = "#252A38"

    # Text
    TEXT = "#E5E7EB"
    TEXT_DIM = "#94A3B8"

    # Accent
    ACCENT = "#7DD3FC"

    # Status (high-contrast through safety glasses)
    OK = "#A3E635"
    WARN = "#FBBF24"
    ERROR = "#FB7185"


class Radius:
    SM = 4
    MD = 8
    LG = 16


class Space:
    XS = 4
    SM = 8
    MD = 16
    LG = 24
    XL = 32
