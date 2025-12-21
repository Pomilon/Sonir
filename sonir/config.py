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
        "high": (70, 180, 220),  # Cyan-ish for Highs
        "kick": (255, 60, 60),  # Bright Red
        "sub": (100, 50, 200),  # Deep Purple
        "mid": (50, 200, 150),  # Teal
        "mel": (255, 200, 50),  # Gold
        "violin": (230, 140, 40), # Amber / Wood
        "air": (200, 240, 255),   # Very Pale Blue
        "upper": (150, 100, 220), # Purple
        "snare": (50, 200, 100),  # Crisp Green
        "hats": (255, 255, 200)   # Pale Yellow
    }

    # Offsets (in seconds)
    OFFSETS = {
        "drums": 0.0,
        "bass": -0.02,
        "other": -0.01,
        "vocals": -0.03
    }

    # Visual Effects
    ENABLE_PARTICLES = True
    ENABLE_SHAKE = True
    ENABLE_TRAILS = True
    ENABLE_GLOW = True
    
    # Dynamic Background
    ENABLE_DYNAMIC_BG = True
    BG_PULSE_AMT = 8         # Subtle brightness boost on hit
    STAR_COUNT = 50          # Stars per viewport
    
    # Camera
    ENABLE_CINEMA_CAM = True
    CAM_LOOKAHEAD = 0.15     # Seconds to look ahead
    
    # UI
    ENABLE_UI = True
    
    # Themes
    THEMES = {
        "neon": { # Default
            "bg": (12, 14, 20),
            "colors": {
                "drums": (220, 80, 70), "bass": (100, 200, 100), "other": (70, 180, 220), "vocals": (200, 100, 220),
                "piano": (255, 255, 255), "low_mid": (100, 150, 200), "high_mid": (150, 100, 220), "treble": (80, 200, 220),
                "low": (220, 80, 70), "high": (70, 180, 220), "kick": (255, 60, 60), "sub": (100, 50, 200),
                "mid": (50, 200, 150), "mel": (255, 200, 50), "violin": (230, 140, 40), 
                "air": (200, 240, 255), "upper": (150, 100, 220), "snare": (50, 200, 100), "hats": (255, 255, 200),
                "top": (255, 255, 255)
            }
        },
        "cyberpunk": {
            "bg": (5, 0, 10),
            "colors": {
                "default": (0, 255, 255) # Cyan fallback
            }
        },
        "noir": {
            "bg": (0, 0, 0),
            "colors": {
                "default": (200, 200, 200) # White/Grey fallback
            }
        },
        "sunset": {
            "bg": (20, 10, 30),
            "colors": {
                "default": (255, 100, 50) # Orange fallback
            }
        },
        "matrix": {
            "bg": (0, 10, 0),
            "colors": {
                "default": (0, 255, 50) # Green fallback
            }
        }
    }

    @staticmethod
    def apply_theme(theme_name):
        if theme_name not in Config.THEMES:
            print(f"Warning: Unknown theme '{theme_name}'. Using default.")
            return

        t = Config.THEMES[theme_name]
        Config.COLOR_BG = t["bg"]
        
        # Helper to generate palette based on theme vibe
        def get_col(key):
            if "colors" in t and key in t["colors"]: return t["colors"][key]
            if "default" in t["colors"]: 
                base = t["colors"]["default"]
                return base
            return (255, 255, 255)

        # Update specific palettes
        if theme_name == "cyberpunk":
            # Cyan & Magenta & Neon Green
            Config.TRACK_COLORS["drums"] = (255, 0, 100)  # Magenta
            Config.TRACK_COLORS["bass"] = (0, 255, 255)   # Cyan
            Config.TRACK_COLORS["kick"] = (255, 0, 100)
            Config.TRACK_COLORS["sub"] = (100, 0, 255)    # Purple
            Config.TRACK_COLORS["snare"] = (0, 255, 100)  # Green
            Config.TRACK_COLORS["hats"] = (255, 255, 0)   # Yellow
            Config.TRACK_COLORS["mel"] = (0, 255, 255)
            Config.TRACK_COLORS["top"] = (255, 0, 255)
            
        elif theme_name == "sunset":
            # Vaporwave / Outrun
            Config.TRACK_COLORS["drums"] = (255, 50, 50)  # Red
            Config.TRACK_COLORS["bass"] = (100, 0, 150)   # Deep Purple
            Config.TRACK_COLORS["kick"] = (255, 100, 0)   # Orange
            Config.TRACK_COLORS["sub"] = (80, 0, 100)
            Config.TRACK_COLORS["mel"] = (255, 200, 100)  # Peach
            Config.TRACK_COLORS["hats"] = (255, 100, 150) # Pink
            Config.TRACK_COLORS["top"] = (255, 200, 100)

        elif theme_name in ["noir", "matrix"]:
            # Monochrome overrides
            c = t["colors"]["default"]
            for k in Config.TRACK_COLORS:
                Config.TRACK_COLORS[k] = c

    # Particle Settings
    PARTICLE_COUNT = 8       # Particles per hit
    PARTICLE_SPEED = 200.0   # Pixel speed
    PARTICLE_DECAY = 2.0     # Life lost per second
    PARTICLE_SIZE = 4
    
    # Trails
    TRAIL_LENGTH = 15        # Number of history points
    
    # Screen Shake
    SHAKE_INTENSITY = 28.0   # Balanced intensity
    SHAKE_DECAY = 5.0        # Snappy decay
    SHAKE_THRESHOLD = 0.91   # Trigger threshold

    @staticmethod
    def set_resolution(aspect_ratio, base=720):
        """
        Updates WIDTH and HEIGHT based on the provided aspect ratio string.
        Supported: '16:9', '9:16', '1:1', '4:3', '21:9'
        """
        ratios = {
            "16:9": (16, 9),
            "9:16": (9, 16),
            "1:1": (1, 1),
            "4:3": (4, 3),
            "21:9": (21, 9)
        }
        
        if aspect_ratio not in ratios:
            print(f"Warning: Unknown aspect ratio '{aspect_ratio}'. Defaulting to 16:9.")
            w_ratio, h_ratio = 16, 9
        else:
            w_ratio, h_ratio = ratios[aspect_ratio]
        
        if w_ratio > h_ratio: # Landscape
            Config.HEIGHT = base
            Config.WIDTH = int(base * (w_ratio / h_ratio))
        else: # Portrait or Square
            Config.WIDTH = base
            Config.HEIGHT = int(base * (h_ratio / w_ratio))
            
        print(f"Resolution set to {Config.WIDTH}x{Config.HEIGHT} ({aspect_ratio})")
