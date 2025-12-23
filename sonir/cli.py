import argparse
import os
import sys
from .config import Config
from .analyzer import StemMode, PianoMode, MultiBandMode, TwoBandMode, KickBassMode, SpectrumMode, ViolinMode, FiveBandMode, DrumsMode, DynamicMode
from .core import SonirCore
from .renderer import SonirRenderer
from .video import VideoGenerator

def main():
    parser = argparse.ArgumentParser(description="Sonir: Modular Audio Visualizer Engine")
    parser.add_argument("--audio", required=True, help="Path to the input audio file")
    parser.add_argument("--mode", choices=["stem", "piano", "multiband", "twoband", "kickbass", "spectrum", "violin", "fiveband", "drums", "dynamic"], default="stem", help="Visualization mode")
    parser.add_argument("--theme", choices=["neon", "cyberpunk", "noir", "sunset", "matrix"], default="neon", help="Color theme")
    parser.add_argument("--aspect", choices=["16:9", "9:16", "1:1", "4:3", "21:9"], default="16:9", help="Output aspect ratio (default: 16:9)")
    parser.add_argument("--export", action="store_true", help="Render to video file instead of realtime preview")
    parser.add_argument("--output", default="output.mp4", help="Output filename for export")
    parser.add_argument("--no-shake", action="store_true", help="Disable screen shake effects")
    parser.add_argument("--no-particles", action="store_true", help="Disable hit particle effects")
    parser.add_argument("--no-trails", action="store_true", help="Disable motion trails")
    parser.add_argument("--no-glow", action="store_true", help="Disable bloom/glow effects")
    parser.add_argument("--no-bg", action="store_true", help="Disable dynamic background (stars/pulse)")
    parser.add_argument("--no-cam", action="store_true", help="Disable cinema camera lookahead")
    parser.add_argument("--no-ui", action="store_true", help="Disable UI overlay")
    
    args = parser.parse_args()
    
    # Configure Resolution & FX
    Config.set_resolution(args.aspect)
    Config.apply_theme(args.theme)
    
    if args.no_shake: Config.ENABLE_SHAKE = False
    if args.no_particles: Config.ENABLE_PARTICLES = False
    if args.no_trails: Config.ENABLE_TRAILS = False
    if args.no_glow: Config.ENABLE_GLOW = False
    if args.no_bg: Config.ENABLE_DYNAMIC_BG = False
    if args.no_cam: Config.ENABLE_CINEMA_CAM = False
    if args.no_ui: Config.ENABLE_UI = False
    
    if not os.path.exists(args.audio):
        print(f"Error: Audio file '{args.audio}' not found.")
        sys.exit(1)

    # 1. Analyze Audio
    print(f"Initializing {args.mode} mode analysis...")
    analyzers = {
        "stem": StemMode,
        "piano": PianoMode,
        "multiband": MultiBandMode,
        "twoband": TwoBandMode,
        "kickbass": KickBassMode,
        "spectrum": SpectrumMode,
        "violin": ViolinMode,
        "fiveband": FiveBandMode,
        "drums": DrumsMode,
        "dynamic": DynamicMode
    }
    
    analyzer_cls = analyzers[args.mode]
    analyzer = analyzer_cls(args.audio)
    
    try:
        raw_tracks = analyzer.analyze()
    except Exception as e:
        print(f"Analysis failed: {e}")
        # Print stack trace for debugging
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    if not raw_tracks:
        print("No tracks found or analysis returned empty results.")
        sys.exit(1)

    # 2. Bake Physics
    print("Baking physics simulations...")
    processed_tracks = {}
    
    # Generate a seed based on audio filename to ensure determinism across runs
    import hashlib
    file_hash = int(hashlib.md5(os.path.basename(args.audio).encode()).hexdigest(), 16) % (2**32)
    
    for name, data in raw_tracks.items():
        print(f"  Baking {name} ({len(data['onsets'])} onsets)...")
        # Mix file hash with track name hash for unique seeds per track but deterministic overall
        track_seed = (file_hash + int(hashlib.md5(name.encode()).hexdigest(), 16)) % (2**32)
        
        timeline, baked_onsets = SonirCore.bake(data['onsets'], seed=track_seed)
        
        processed_tracks[name] = {
            "timeline": timeline,
            "onsets": baked_onsets,
            "color": data['color'],
            "path": data['path']
        }

    # 3. Render
    renderer = SonirRenderer(processed_tracks, args.audio)
    
    if args.export:
        print("Starting headless render...")
        frames_dir = "sonir_frames_tmp"
        renderer.run_headless(output_dir=frames_dir)
        
        # 4. Video Generation
        VideoGenerator.generate(args.audio, frames_dir, args.output, Config.HEADLESS_FPS)
        
        # Cleanup
        import shutil
        shutil.rmtree(frames_dir)
        print("Done.")
    else:
        print("Starting realtime preview...")
        renderer.run_realtime()

if __name__ == "__main__":
    main()
