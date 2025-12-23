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
        delta = kwargs.pop('delta', 0.07) # Librosa default
        wait = kwargs.pop('wait', 2) # Reduced default for fast note chaining
        pre_max = kwargs.pop('pre_max', 3) # Reduced window for local peaks
        post_max = kwargs.pop('post_max', 3)
        
        # Calculate onset envelope
        # Only pass remaining kwargs (like fmin, fmax) to onset_strength
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
        
        # If density is too low (< 0.5 per second), it might be an ambient/soft track.
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
            
            kwargs = {}
            if name == "drums":
                kwargs['fmin'] = 500 # Focus on high freq transients
                kwargs['wait'] = 1   # Catch fast rolls/drills
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
            wait=1
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
                
            S_db = librosa.amplitude_to_db(spec, ref=np.max)
            onsets = self._get_onsets(y=y, sr=sr, S=S_db, wait=2)
            
            results[name] = {
                "onsets": onsets,
                "color": Config.TRACK_COLORS.get(name, (255, 255, 255)),
                "path": self.audio_path
            }
            
        return results

class KickBassMode(AudioAnalyzer):
    def analyze(self):
        print("Analyzing KickBass Mode (Electronic Focus)...")
        y, sr = librosa.load(self.audio_path)
        D = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        
        # 1. Kick/Sub (Very Low) - Focus on the 'thump'
        # 2. Top (Everything else) - Snare, Hats, Melody
        bands = [
            ("kick", 20, 150, 2),      # Deep lows, faster response
            ("top", 150, 8000, 1)     # The rest, rapid response
        ]
        
        results = {}
        
        for name, low, high, wait_val in bands:
            mask = (freqs >= low) & (freqs <= high)
            spec = D[mask, :]
            if spec.shape[0] == 0: continue

            S_db = librosa.amplitude_to_db(spec, ref=np.max)
            onsets = self._get_onsets(y=y, sr=sr, S=S_db, wait=wait_val)
            
            # Map 'top' to a color if not defined, or reuse 'high'
            col = Config.TRACK_COLORS.get(name, Config.TRACK_COLORS["high"] if name == "top" else (255,255,255))
            
            results[name] = {
                "onsets": onsets,
                "color": col,
                "path": self.audio_path
            }
        return results

class SpectrumMode(AudioAnalyzer):
    def analyze(self):
        print("Analyzing Spectrum Mode (3-Band Split)...")
        y, sr = librosa.load(self.audio_path)
        D = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        
        # Classic 3-band split
        bands = [
            ("sub", 20, 250, 2),
            ("mid", 250, 2000, 2),
            ("mel", 2000, 8000, 2) # High/Melody
        ]
        
        results = {}
        for name, low, high, wait_val in bands:
            mask = (freqs >= low) & (freqs <= high)
            spec = D[mask, :]
            if spec.shape[0] == 0: continue

            S_db = librosa.amplitude_to_db(spec, ref=np.max)
            onsets = self._get_onsets(y=y, sr=sr, S=S_db, wait=wait_val)
            
            results[name] = {
                "onsets": onsets,
                "color": Config.TRACK_COLORS.get(name, (255, 255, 255)),
                "path": self.audio_path
            }
        return results

class FiveBandMode(AudioAnalyzer):
    def analyze(self):
        print("Analyzing Five-Band Mode (Center Focus)...")
        y, sr = librosa.load(self.audio_path)
        D = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        
        # Order determines position in the 5-viewport layout:
        # 1. TL (Air), 2. TR (Upper), 3. BL (Sub), 4. BR (Bass), 5. Center (Mid)
        bands = [
            ("air", 5000, 10000, 1),    # Top Left
            ("upper", 2000, 5000, 2),   # Top Right
            ("sub", 20, 100, 4),        # Bottom Left
            ("bass", 100, 300, 3),      # Bottom Right
            ("mid", 300, 2000, 2)       # Center (Focus)
        ]
        
        results = {}
        for name, low, high, wait_val in bands:
            mask = (freqs >= low) & (freqs <= high)
            spec = D[mask, :]
            if spec.shape[0] == 0: continue

            S_db = librosa.amplitude_to_db(spec, ref=np.max)
            onsets = self._get_onsets(y=y, sr=sr, S=S_db, wait=wait_val)
            
            # Colors
            if name == "air": col = Config.TRACK_COLORS["air"]
            elif name == "upper": col = Config.TRACK_COLORS["upper"]
            elif name == "sub": col = Config.TRACK_COLORS["kick"] # Reuse kick color
            elif name == "bass": col = Config.TRACK_COLORS["bass"]
            else: col = Config.TRACK_COLORS["mel"] # Mid/Lead gets gold
            
            results[name] = {
                "onsets": onsets,
                "color": col,
                "path": self.audio_path
            }
        return results

class DrumsMode(AudioAnalyzer):
    def analyze(self):
        print("Analyzing Drums Mode (Percussion Focus)...")
        y, sr = librosa.load(self.audio_path)
        D = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        
        # 3-Band Percussion Split
        # Kick: Deep lows
        # Snare: Mid-range body
        # Hats: High transients
        bands = [
            ("kick", 20, 150, 1),
            ("snare", 150, 2000, 1),
            ("hats", 2000, 10000, 1)
        ]
        
        results = {}
        for name, low, high, wait_val in bands:
            mask = (freqs >= low) & (freqs <= high)
            spec = D[mask, :]
            if spec.shape[0] == 0: continue

            S_db = librosa.amplitude_to_db(spec, ref=np.max)
            onsets = self._get_onsets(y=y, sr=sr, S=S_db, wait=wait_val)
            
            results[name] = {
                "onsets": onsets,
                "color": Config.TRACK_COLORS.get(name, (255, 255, 255)),
                "path": self.audio_path
            }
        return results

class ViolinMode(AudioAnalyzer):
    def analyze(self):
        print("Analyzing Violin Mode (Solo Focus)...")
        y, sr = librosa.load(self.audio_path)
        
        # STFT
        D = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        
        # Mask: 190Hz (G3) to 10kHz (Harmonics/Bow noise)
        mask = (freqs > 190) & (freqs < 10000)
        S_filtered = D[mask, :]
        
        if S_filtered.shape[0] == 0:
            print("Warning: No violin frequencies detected.")
            S_db = librosa.amplitude_to_db(D, ref=np.max)
        else:
            S_db = librosa.amplitude_to_db(S_filtered, ref=np.max)
            
        # Detect onsets with moderate wait to handle bowing
        onsets = self._get_onsets(y=y, sr=sr, S=S_db, wait=2)
        
        return {
            "violin": {
                "onsets": onsets,
                "color": Config.TRACK_COLORS["violin"],
                "path": self.audio_path
            }
        }

class DynamicMode(AudioAnalyzer):
    def analyze(self):
        print("Analyzing Dynamic Mode (HPSS + Band Separation)...")
        y, sr = librosa.load(self.audio_path)
        
        # 1. Harmonic-Percussive Source Separation
        print("  Separating Harmonic and Percussive components...")
        y_harm, y_perc = librosa.effects.hpss(y)
        
        results = {}
        
        # 2. Analyze Percussive Stream (Rhythm)
        # Split into Low (Kick) and Mid/High (Snare/Hats)
        # Using separate frequency bands on the percussive signal is very clean.
        
        # We need spectrogram for frequency masking
        D_perc = np.abs(librosa.stft(y_perc))
        freqs = librosa.fft_frequencies(sr=sr)
        
        # Percussive Bands
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
            # Use lower delta for percussive elements as they are distinct peaks
            onsets = self._get_onsets(y=None, sr=sr, S=S_db, wait=wait_val, delta=0.06)
            
            results[name] = {
                "onsets": onsets,
                "color": Config.TRACK_COLORS.get(name, (255, 255, 255)),
                "path": self.audio_path
            }
            
        # 3. Analyze Harmonic Stream (Melody/Chords)
        # We treat this as one or two bands.
        
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
            # Use higher delta/wait for harmonic content to avoid noise
            onsets = self._get_onsets(y=None, sr=sr, S=S_db, wait=wait_val, delta=0.1)
            
            results[name] = {
                "onsets": onsets,
                "color": Config.TRACK_COLORS.get(name, (200, 200, 200)),
                "path": self.audio_path
            }
            
        return results
