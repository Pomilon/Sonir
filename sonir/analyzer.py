import os
import subprocess
import librosa
import numpy as np
from .config import Config

class AudioAnalyzer:
    def __init__(self, audio_path):
        self.audio_path = audio_path
        self.sr = 22050 # Default Librosa SR
        self.duration = 0

    def analyze(self):
        """
        Returns a dictionary of tracks.
        Format:
        {
            "track_name": {
                "onsets": np.array([...]),
                "color": (r, g, b),
                "audio_path": "path/to/source.wav" (optional, for playback mixing if needed)
            }
        }
        """
        raise NotImplementedError

    def _get_onsets(self, y, sr, offset=0.0, **kwargs):
        """Standardized onset detection with adaptive sensitivity."""
        # Initial parameters
        delta = kwargs.get('delta', 0.07) # Librosa default
        wait = kwargs.get('wait', 6)
        pre_max = kwargs.get('pre_max', 5)
        post_max = kwargs.get('post_max', 5)
        
        # Calculate onset envelope
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, **kwargs)
        
        # Detect onsets
        onsets = librosa.onset.onset_detect(
            onset_envelope=onset_env, 
            sr=sr, 
            units='time', 
            backtrack=True, 
            wait=wait,
            pre_max=pre_max,
            post_max=post_max,
            delta=delta
        )
        
        # Adaptive Sensitivity Check
        # Calculate density (onsets per second)
        duration = 0
        if y is not None:
            duration = len(y) / sr
        elif kwargs.get('S') is not None:
            # Approximate duration from spectrogram (default hop_length=512)
            duration = kwargs['S'].shape[1] * kwargs.get('hop_length', 512) / sr

        density = len(onsets) / duration if duration > 0 else 0
        
        # If density is too low (e.g., < 0.5 per second), it might be an ambient/soft track.
        # Retry with higher sensitivity.
        if density < 0.5 and duration > 5.0:
            print(f"  Low onset density ({density:.2f}/s). Retrying with high sensitivity...")
            
            # Boost sensitivity: Lower delta significantly, reduce wait
            delta_sensitive = delta * 0.4 
            wait_sensitive = max(1, wait // 2)
            
            onsets = librosa.onset.onset_detect(
                onset_envelope=onset_env, 
                sr=sr, 
                units='time', 
                backtrack=True, 
                wait=wait_sensitive,
                pre_max=pre_max,
                post_max=post_max,
                delta=delta_sensitive
            )
            print(f"  -> Found {len(onsets)} onsets (Density: {len(onsets)/duration:.2f}/s)")

        # Apply offset
        return onsets + offset

class StemMode(AudioAnalyzer):
    def analyze(self):
        song_name = os.path.splitext(os.path.basename(self.audio_path))[0]
        # Assuming standard Demucs output structure
        base_path = os.path.join("separated", "htdemucs", song_name)
        
        # Check if separation is needed
        needs_separation = False
        if not os.path.exists(base_path):
            needs_separation = True
        else:
            # Check for individual files
            for stem in ["drums.wav", "bass.wav", "other.wav", "vocals.wav"]:
                if not os.path.exists(os.path.join(base_path, stem)):
                    needs_separation = True
                    break
                    
        if needs_separation:
            print(f"Separated tracks not found for '{song_name}'. Running Demucs...")
            try:
                # Run demucs command
                # -n htdemucs: Use the standard high-quality model
                cmd = ["demucs", "-n", "htdemucs", self.audio_path]
                subprocess.run(cmd, check=True)
                print("Demucs separation complete.")
            except subprocess.CalledProcessError as e:
                print(f"Error running Demucs: {e}")
                print("Make sure 'demucs' is installed via 'pip install demucs'.")
                return {}
            except FileNotFoundError:
                print("Demucs executable not found. Please install it with 'pip install demucs'.")
                return {}
        
        tracks_info = {
            "drums": {"offset": Config.OFFSETS["drums"], "color": Config.TRACK_COLORS["drums"]},
            "bass": {"offset": Config.OFFSETS["bass"], "color": Config.TRACK_COLORS["bass"]},
            "other": {"offset": Config.OFFSETS["other"], "color": Config.TRACK_COLORS["other"]},
            "vocals": {"offset": Config.OFFSETS["vocals"], "color": Config.TRACK_COLORS["vocals"]}
        }
        
        results = {}
        
        for name, info in tracks_info.items():
            path = os.path.join(base_path, f"{name}.wav")
            if not os.path.exists(path):
                print(f"Warning: Stem {name} not found at {path}. Skipping.")
                continue
                
            print(f"Analyzing stem: {name}...")
            y, sr = librosa.load(path, sr=None) # Load at native SR
            
            # Specific tuning per stem (from main_split_all_improved.py)
            kwargs = {}
            if name == "drums":
                kwargs['fmin'] = 500 # Focus on high freq transients
            elif name == "bass":
                kwargs['fmax'] = 150 # Focus on low freq
                
            onsets = self._get_onsets(y, sr, offset=info['offset'], **kwargs)
            
            results[name] = {
                "onsets": onsets,
                "color": info['color'],
                "path": path
            }
            
        return results

class PianoMode(AudioAnalyzer):
    def analyze(self):
        print("Analyzing Piano Mode (Transient Focus)...")
        y, sr = librosa.load(self.audio_path)
        
        # STFT and Frequency Masking (from main.py)
        S = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        
        # Mask: 400Hz - 4500Hz
        mask = (freqs > 400) & (freqs < 4500)
        S_piano = S[mask, :]
        
        # Calculate strength from masked spectrogram
        onset_env = librosa.onset.onset_strength(S=librosa.amplitude_to_db(S_piano), sr=sr)
        
        # Detect
        onsets = librosa.onset.onset_detect(
            onset_envelope=onset_env, 
            sr=sr, 
            units='time', 
            backtrack=True, 
            wait=2
        )
        
        return {
            "piano": {
                "onsets": onsets,
                "color": Config.TRACK_COLORS["piano"],
                "path": self.audio_path
            }
        }

class MultiBandMode(AudioAnalyzer):
    def analyze(self):
        print("Analyzing Multi-Band Mode...")
        y, sr = librosa.load(self.audio_path)
        D = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        
        # (name, low, high, wait_param)
        # Use lower wait for high frequencies to catch fast arpeggios
        bands = [
            ("bass", 20, 250, 4),
            ("low_mid", 250, 1000, 4),
            ("high_mid", 1000, 3000, 2), # Faster response for melody
            ("treble", 3000, 8000, 1)    # Fastest response for hihats/glitter
        ]
        
        results = {}
        
        for name, low, high, wait_val in bands:
            mask = (freqs >= low) & (freqs <= high)
            spec = D[mask, :]
            
            if spec.shape[0] == 0:
                continue
            
            # Calculate dB spec
            S_db = librosa.amplitude_to_db(spec, ref=np.max)
            
            onsets = self._get_onsets(
                y=y, 
                sr=sr, 
                S=S_db, 
                wait=wait_val
            )
            
            results[name] = {
                "onsets": onsets,
                "color": Config.TRACK_COLORS.get(name, (255, 255, 255)),
                "path": self.audio_path
            }
            
        return results

class TwoBandMode(AudioAnalyzer):
    def analyze(self):
        print("Analyzing Two-Band Mode (Low/High)...")
        y, sr = librosa.load(self.audio_path)
        D = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        
        # Split roughly at 800Hz
        bands = [
            ("low", 20, 800),
            ("high", 800, 8000)
        ]
        
        results = {}
        
        for name, low, high in bands:
            mask = (freqs >= low) & (freqs <= high)
            spec = D[mask, :]
            
            if spec.shape[0] == 0:
                continue
                
            onset_env = librosa.onset.onset_strength(S=librosa.amplitude_to_db(spec), sr=sr)
            onsets = librosa.onset.onset_detect(
                onset_envelope=onset_env, 
                sr=sr, 
                units='time', 
                backtrack=True, 
                wait=4
            )
            
            results[name] = {
                "onsets": onsets,
                "color": Config.TRACK_COLORS.get(name, (255, 255, 255)),
                "path": self.audio_path
            }
            
        return results
