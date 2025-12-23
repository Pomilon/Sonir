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
                "audio_path": "path/to/source.wav" (optional)
            }
        }
        """
        raise NotImplementedError

    def _load_audio(self, path=None, sr=None):
        """Safely load audio file."""
        target_path = path if path else self.audio_path
        target_sr = sr if sr else self.sr
        try:
            y, sr_out = librosa.load(target_path, sr=target_sr)
            return y, sr_out
        except Exception as e:
            print(f"Error loading audio file '{target_path}': {e}")
            return None, None

    def _get_onsets(self, y, sr, offset=0.0, **kwargs):
        """Standardized onset detection with adaptive sensitivity."""
        # Initial parameters
        delta = kwargs.pop('delta', 0.07) # Librosa default
        wait = kwargs.pop('wait', 2) # Reduced default for fast note chaining
        pre_max = kwargs.pop('pre_max', 3) # Reduced window for local peaks
        post_max = kwargs.pop('post_max', 3)
        
        # Calculate onset envelope
        # Only pass remaining kwargs (like fmin, fmax) to onset_strength
        try:
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
        except Exception as e:
            print(f"Error during onset detection: {e}")
            return np.array([])
        
        # Adaptive Sensitivity Check
        # Calculate density (onsets per second)
        duration = 0
        if y is not None:
            duration = len(y) / sr
        elif kwargs.get('S') is not None:
            # Approximate duration from spectrogram (default hop_length=512)
            duration = kwargs['S'].shape[1] * kwargs.get('hop_length', 512) / sr

        density = len(onsets) / duration if duration > 0 else 0
        
        # If density is too low (< 0.5 per second), it might be an ambient/soft track.
        # Retry with higher sensitivity.
        if density < 0.5 and duration > 5.0:
            print(f"  Low onset density ({density:.2f}/s). Retrying with high sensitivity...")
            
            # Boost sensitivity: Lower delta significantly, reduce wait
            delta_sensitive = delta * 0.4 
            wait_sensitive = max(1, wait // 2)
            
            try:
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
            except Exception:
                pass # Fallback to original onsets

        # Apply offset
        return onsets + offset

class FrequencyBandMode(AudioAnalyzer):
    """
    Base class for modes that split audio into frequency bands using STFT.
    """
    def __init__(self, audio_path, bands):
        """
        bands: List of tuples (name, low_freq, high_freq, wait_val)
        """
        super().__init__(audio_path)
        self.bands = bands

    def analyze(self):
        print(f"Analyzing {self.__class__.__name__}...")
        y, sr = self._load_audio()
        if y is None: return {}

        D = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        
        results = {}
        
        for name, low, high, wait_val in self.bands:
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
            
            # Handle alias color keys (e.g., 'top' -> 'high')
            col = Config.TRACK_COLORS.get(name, (255, 255, 255))
            if name == "top" and "top" not in Config.TRACK_COLORS:
                col = Config.TRACK_COLORS.get("high", (255, 255, 255))

            results[name] = {
                "onsets": onsets,
                "color": col,
                "path": self.audio_path
            }
            
        return results

# --- Concrete Implementations ---

class QuadBandMode(FrequencyBandMode):
    def __init__(self, audio_path):
        super().__init__(audio_path, [
            ("bass", 20, 250, 4),
            ("low_mid", 250, 1000, 4),
            ("high_mid", 1000, 3000, 2), 
            ("treble", 3000, 8000, 1)
        ])

class TripleBandMode(FrequencyBandMode):
    def __init__(self, audio_path):
        super().__init__(audio_path, [
            ("sub", 20, 250, 2),
            ("mid", 250, 2000, 2),
            ("mel", 2000, 8000, 2)
        ])

class DualBandMode(FrequencyBandMode):
    def __init__(self, audio_path):
        super().__init__(audio_path, [
            ("low", 20, 800, 2),
            ("high", 800, 8000, 2)
        ])

class ElectronicMode(FrequencyBandMode):
    def __init__(self, audio_path):
        super().__init__(audio_path, [
            ("kick", 20, 150, 2),
            ("top", 150, 8000, 1)
        ])

class CinematicMode(FrequencyBandMode):
    def __init__(self, audio_path):
        # Order implies layout in renderer (TL, TR, BL, BR, Center)
        super().__init__(audio_path, [
            ("air", 5000, 10000, 1),
            ("upper", 2000, 5000, 2),
            ("sub", 20, 100, 4),
            ("bass", 100, 300, 3),
            ("mid", 300, 2000, 2)
        ])

class PercussionMode(FrequencyBandMode):
    def __init__(self, audio_path):
        super().__init__(audio_path, [
            ("kick", 20, 150, 1),
            ("snare", 150, 2000, 1),
            ("hats", 2000, 10000, 1)
        ])

class StringMode(AudioAnalyzer):
    def analyze(self):
        print("Analyzing String Mode (Solo Focus)...")
        y, sr = self._load_audio()
        if y is None: return {}
        
        D = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        
        # Mask: 190Hz (G3) to 10kHz (Harmonics/Bow noise)
        mask = (freqs > 190) & (freqs < 10000)
        S_filtered = D[mask, :]
        
        if S_filtered.shape[0] == 0:
            print("Warning: No string frequencies detected.")
            S_db = librosa.amplitude_to_db(D, ref=np.max)
        else:
            S_db = librosa.amplitude_to_db(S_filtered, ref=np.max)
            
        onsets = self._get_onsets(y=y, sr=sr, S=S_db, wait=2)
        
        return {
            "strings": {
                "onsets": onsets,
                "color": Config.TRACK_COLORS.get("strings", (230, 140, 40)),
                "path": self.audio_path
            }
        }

class PianoMode(AudioAnalyzer):
    def analyze(self):
        print("Analyzing Piano Mode (Transient Focus)...")
        y, sr = self._load_audio()
        if y is None: return {}
        
        # STFT and Frequency Masking
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
            wait=1
        )
        
        return {
            "piano": {
                "onsets": onsets,
                "color": Config.TRACK_COLORS["piano"],
                "path": self.audio_path
            }
        }

class DynamicMode(AudioAnalyzer):
    def analyze(self):
        print("Analyzing Dynamic Mode (HPSS + Band Separation)...")
        y, sr = self._load_audio()
        if y is None: return {}
        
        # 1. Harmonic-Percussive Source Separation
        print("  Separating Harmonic and Percussive components...")
        y_harm, y_perc = librosa.effects.hpss(y)
        
        results = {}
        
        # 2. Analyze Percussive Stream (Rhythm)
        # Split into Low (Kick) and Mid/High (Snare/Hats)
        D_perc = np.abs(librosa.stft(y_perc))
        freqs = librosa.fft_frequencies(sr=sr)
        
        p_bands = [
            ("kick", 20, 150, 2),       # Deep Hits
            ("snare", 150, 2500, 1),    # Snare/Clap
            ("hats", 2500, 10000, 1)    # Cymbals/Hats
        ]
        
        for name, low, high, wait_val in p_bands:
            mask = (freqs >= low) & (freqs <= high)
            spec = D_perc[mask, :]
            if spec.shape[0] == 0: continue
            
            S_db = librosa.amplitude_to_db(spec, ref=np.max)
            onsets = self._get_onsets(y=None, sr=sr, S=S_db, wait=wait_val, delta=0.06)
            
            results[name] = {
                "onsets": onsets,
                "color": Config.TRACK_COLORS.get(name, (255, 255, 255)),
                "path": self.audio_path
            }
            
        # 3. Analyze Harmonic Stream (Melody/Chords)
        D_harm = np.abs(librosa.stft(y_harm))
        
        h_bands = [
            ("bass", 20, 300, 4),        # Bassline (Sustained)
            ("mel", 300, 5000, 4)        # Chords/Melody
        ]
        
        for name, low, high, wait_val in h_bands:
            mask = (freqs >= low) & (freqs <= high)
            spec = D_harm[mask, :]
            if spec.shape[0] == 0: continue
            
            S_db = librosa.amplitude_to_db(spec, ref=np.max)
            onsets = self._get_onsets(y=None, sr=sr, S=S_db, wait=wait_val, delta=0.1)
            
            results[name] = {
                "onsets": onsets,
                "color": Config.TRACK_COLORS.get(name, (200, 200, 200)),
                "path": self.audio_path
            }
            
        return results

class StemMode(AudioAnalyzer):
    def analyze(self):
        song_name = os.path.splitext(os.path.basename(self.audio_path))[0]
        base_path = os.path.join("separated", "htdemucs", song_name)
        
        # Check if separation is needed
        needs_separation = False
        if not os.path.exists(base_path):
            needs_separation = True
        else:
            for stem in ["drums.wav", "bass.wav", "other.wav", "vocals.wav"]:
                if not os.path.exists(os.path.join(base_path, stem)):
                    needs_separation = True
                    break
                    
        if needs_separation:
            print(f"Separated tracks not found for '{song_name}'. Running Demucs...")
            try:
                # Run demucs command
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
            y, sr = self._load_audio(path=path)
            if y is None: continue
            
            kwargs = {}
            if name == "drums":
                kwargs['fmin'] = 500 
                kwargs['wait'] = 1   
            elif name == "bass":
                kwargs['fmax'] = 150 
                
            onsets = self._get_onsets(y, sr, offset=info['offset'], **kwargs)
            
            results[name] = {
                "onsets": onsets,
                "color": info['color'],
                "path": path
            }
            
        return results