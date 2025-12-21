import subprocess
import os

class VideoGenerator:
    @staticmethod
    def generate(audio_path, frame_dir, output_path, fps):
        print("Stitching video with FFmpeg...")
        
        frame_pattern = os.path.join(frame_dir, "frame_%05d.png")
        
        cmd = [
            "ffmpeg",
            "-y", # Overwrite
            "-framerate", str(fps),
            "-i", frame_pattern,
            "-i", audio_path,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "18", # High quality
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True)
            print(f"Video saved to {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg failed: {e}")
        except FileNotFoundError:
            print("FFmpeg not found. Please install ffmpeg.")
