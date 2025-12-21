import argparse
import os
import sys
from .config import Config
from .analyzer import StemMode, PianoMode, MultiBandMode, TwoBandMode
from .core import SonirCore
from .renderer import SonirRenderer
from .video import VideoGenerator

def main():
    parser = argparse.ArgumentParser(description="Sonir: Modular Audio Visualizer Engine")
    parser.add_argument("--audio", required=True, help="Path to the input audio file")
    parser.add_argument("--mode", choices=["stem", "piano", "multiband", "twoband"], default="stem", help="Visualization mode")
    parser.add_argument("--export", action="store_true", help="Render to video file instead of realtime preview")
    parser.add_argument("--output", default="output.mp4", help="Output filename for export")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.audio):
        print(f"Error: Audio file '{args.audio}' not found.")
        sys.exit(1)

    # 1. Analyze Audio
    print(f"Initializing {args.mode} mode analysis...")
    analyzers = {
        "stem": StemMode,
        "piano": PianoMode,
        "multiband": MultiBandMode,
        "twoband": TwoBandMode
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
    for name, data in raw_tracks.items():
        print(f"  Baking {name} ({len(data['onsets'])} onsets)...")
        timeline, baked_onsets = SonirCore.bake(data['onsets'])
        
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
