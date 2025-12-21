class Config:
    # Display
    WIDTH = 1280
    HEIGHT = 720
    FPS = 60
    HEADLESS_FPS = 60
    
    # Physics
    SQUARE_SPEED = 850.0
    SQUARE_SIZE = 22
    LERP_FACTOR = 0.08
    
    # Colors (R, G, B)
    COLOR_BG = (12, 14, 20)
    COLOR_SQUARE = (240, 240, 240)
    COLOR_SQUARE_BORDER = (45, 50, 65)
    
    # Track defaults
    TRACK_COLORS = {
        "drums": (220, 80, 70),
        "bass": (100, 200, 100),
        "other": (70, 180, 220),
        "vocals": (200, 100, 220),
        "piano": (255, 255, 255),
        "low_mid": (100, 150, 200),
        "high_mid": (150, 100, 220),
        "treble": (80, 200, 220),
        "low": (220, 80, 70),   # Red-ish for Lows
        "high": (70, 180, 220)  # Cyan-ish for Highs
    }

    # Offsets (in seconds)
    OFFSETS = {
        "drums": 0.0,
        "bass": -0.02,
        "other": -0.01,
        "vocals": -0.03
    }
