import pygame
import numpy as np
import os
import shutil
import librosa
from .config import Config

class SonirRenderer:
    def __init__(self, tracks_data, audio_path, width=Config.WIDTH, height=Config.HEIGHT):
        self.tracks_data = tracks_data
        self.audio_path = audio_path
        self.width = width
        self.height = height
        
        # Initialize render state for each track
        # tracks_data structure: { name: { timeline: [], color: ..., ... } }
        self.render_state = {}
        for name in tracks_data:
            self.render_state[name] = {
                "cam": np.array([0.0, 0.0])
            }
            
        # Determine layout
        self.rects = self._calculate_layout(len(tracks_data))
        
    def _calculate_layout(self, num_tracks):
        rects = {}
        track_names = list(self.tracks_data.keys())
        
        if num_tracks == 1:
            rects[track_names[0]] = pygame.Rect(0, 0, self.width, self.height)
        elif num_tracks == 4:
            w, h = self.width // 2, self.height // 2
            # Specific order for stems/bands if present
            order = track_names
            rects[order[0]] = pygame.Rect(0, 0, w, h)
            rects[order[1]] = pygame.Rect(0, h, w, h)
            rects[order[2]] = pygame.Rect(w, 0, w, h)
            rects[order[3]] = pygame.Rect(w, h, w, h)
        else:
            # Fallback for other counts: just stack horizontally
            w = self.width // num_tracks
            for i, name in enumerate(track_names):
                rects[name] = pygame.Rect(i * w, 0, w, self.height)
                
        return rects

    def render_frame(self, surface, audio_time):
        """Draws a single frame to the provided surface."""
        surface.fill(Config.COLOR_BG)
        
        for name, rect in self.rects.items():
            track = self.tracks_data[name]
            state = self.render_state[name]
            
            # Subsurface for clipping
            sub = surface.subsurface(rect)
            
            self._draw_viewport(sub, rect, track, state, audio_time)
            
            # Draw Border
            pygame.draw.rect(surface, Config.COLOR_SQUARE_BORDER, rect, 2)

    def _draw_viewport(self, surface, rect, track, state, audio_time):
        timeline = track["timeline"]
        if not timeline: return
        
        center = np.array([rect.width/2, rect.height/2])
        
        # Using binary search on onsets to find index
        idx = np.searchsorted(track['onsets'], audio_time) - 1
        
        # Clamp index
        if idx < 0: idx = 0
        
        # Interpolate camera
        target_cam = state["cam"]
        
        if 0 <= idx < len(timeline):
            seg = timeline[idx]
            duration = seg['t1'] - seg['t0']
            if duration > 0:
                progress = (audio_time - seg['t0']) / duration
            else:
                progress = 0
                
            sq_world = seg['p0'] + (seg['p1'] - seg['p0']) * progress
            
            # Calculate desired camera position (center focused on square)
            target_cam = center - sq_world
            
        # Smooth camera movement
        state["cam"] += (target_cam - state["cam"]) * Config.LERP_FACTOR
        cam = state["cam"]
        
        # Draw Geometry
        # Draw a range of walls around current time
        draw_range_start = max(0, idx - 5)
        draw_range_end = min(len(timeline), idx + 15)
        
        for i in range(draw_range_start, draw_range_end):
            item = timeline[i]
            p1 = item['w1'] + cam
            p2 = item['w2'] + cam
            
            # Styling
            is_active = (i == idx)
            
            if is_active and 0 <= idx < len(timeline):
                # Recalculate progress for this specific segment
                seg = timeline[idx]
                dur = seg['t1'] - seg['t0']
                prog = (audio_time - seg['t0']) / dur if dur > 0 else 0
                
                if prog > 0.92: # Hit Flash
                    col, w = (255, 255, 255), 12
                else:
                    col, w = track["color"], 7
            elif i < idx:
                col, w = (40, 42, 50), 2 # Past
            else:
                # Future walls - dim version of track color
                c = track["color"]
                col, w = (c[0]//2, c[1]//2, c[2]//2), 4
                
            pygame.draw.line(surface, col, p1, p2, w)
            
        # Draw Square
        if 0 <= idx < len(timeline):
            # Recalculate square pos
            seg = timeline[idx]
            dur = seg['t1'] - seg['t0']
            prog = (audio_time - seg['t0']) / dur if dur > 0 else 0
            sq_world = seg['p0'] + (seg['p1'] - seg['p0']) * prog
            
            sq_pos = sq_world + cam
            sz = Config.SQUARE_SIZE
            pygame.draw.rect(surface, Config.COLOR_SQUARE, 
                             (sq_pos[0]-sz/2, sq_pos[1]-sz/2, sz, sz))


    def run_realtime(self):
        pygame.init()
        screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Sonir Realtime")
        clock = pygame.time.Clock()
        
        # Audio
        pygame.mixer.init()
        pygame.mixer.music.load(self.audio_path)
        pygame.mixer.music.play()
        
        print("Starting realtime render... Press ESC to quit.")
        
        running = True
        while running:
            # Sync
            # get_pos returns ms
            audio_time = pygame.mixer.music.get_pos() / 1000.0
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
            
            self.render_frame(screen, audio_time)
            pygame.display.flip()
            clock.tick(Config.FPS)
            
        pygame.quit()

    def run_headless(self, output_dir="frames"):
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)
        
        pygame.init()
        screen = pygame.display.set_mode((self.width, self.height))
        
        # Get duration
        y, sr = librosa.load(self.audio_path, sr=None)
        duration = librosa.get_duration(y=y, sr=sr)
        
        total_frames = int(duration * Config.HEADLESS_FPS)
        dt = 1.0 / Config.HEADLESS_FPS
        
        print(f"Rendering {total_frames} frames to '{output_dir}'...")
        
        for i in range(total_frames):
            audio_time = i * dt
            self.render_frame(screen, audio_time)
            
            fname = os.path.join(output_dir, f"frame_{i:05d}.png")
            pygame.image.save(screen, fname)
            
            if i % 100 == 0:
                print(f"Rendered {i}/{total_frames} frames ({i/total_frames*100:.1f}%)", end='\r')
                
        print("\nRendering complete.")
        pygame.quit()
