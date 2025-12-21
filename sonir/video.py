import subprocess
import os

class VideoGenerator:
    @staticmethod
    def generate(audio_path, frame_dir, output_path, fps, encoder="libx265", crf=24):
        print(f"Stitching video with FFmpeg (Encoder: {encoder}, CRF: {crf})...")
        
        frame_pattern = os.path.join(frame_dir, "frame_%05d.png")
        
        cmd = [
            "ffmpeg",
            "-y", # Overwrite
            "-framerate", str(fps),
            "-i", frame_pattern,
            "-i", audio_path,
            "-c:v", encoder,
            "-pix_fmt", "yuv420p",
            "-crf", str(crf),
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest"
        ]
        
        # Add Apple compatibility tag for HEVC (H.265)
        if encoder == "libx265":
            cmd.extend(["-tag:v", "hvc1"])
            
        cmd.append(output_path)
        
        try:
            subprocess.run(cmd, check=True)
            print(f"Video saved to {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg failed: {e}")
        except FileNotFoundError:
            print("FFmpeg not found. Please install ffmpeg.")
