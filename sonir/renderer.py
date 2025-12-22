import pygame
import numpy as np
import os
import shutil
import librosa
import math
import random
from .config import Config

class SonirRenderer:
    def __init__(self, tracks_data, audio_path, width=None, height=None):
        self.tracks_data = tracks_data
        self.audio_path = audio_path
        self.width = width if width is not None else Config.WIDTH
        self.height = height if height is not None else Config.HEIGHT
        
        # Audio Duration (for UI)
        y_tmp, sr_tmp = librosa.load(audio_path, sr=None)
        self.duration = librosa.get_duration(y=y_tmp, sr=sr_tmp)
        
        # UI Font
        if pygame.font.get_init() is False: pygame.font.init()
        self.font = pygame.font.SysFont("arial", 14)
        
        # Initialize render state for each track
        # tracks_data structure: { name: { timeline: [], color: ..., ... } }
        self.render_state = {}
        for name in tracks_data:
            # Generate static stars for this viewport
            stars = []
            for _ in range(Config.STAR_COUNT):
                # Store as relative coordinates (0.0-1.0) so they scale with viewport
                stars.append([random.random(), random.random(), random.uniform(0.5, 2.0)]) # x, y, size
                
            self.render_state[name] = {
                "cam": np.array([0.0, 0.0]),
                "particles": [], # List of [pos, vel, life, color]
                "trail": [],     # List of positions [x, y]
                "shake": 0.0,    # Current shake intensity
                "last_hit_idx": -1, # To prevent double triggering on same wall
                "stars": stars
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
        elif num_tracks == 5:
            # 5-Band Layout: 4 Corners + 1 Center Overlay
            w_half, h_half = self.width // 2, self.height // 2
            
            # The background quadrants
            # 0: TL, 1: TR, 2: BL, 3: BR
            rects[track_names[0]] = pygame.Rect(0, 0, w_half, h_half)
            rects[track_names[1]] = pygame.Rect(w_half, 0, w_half, h_half)
            rects[track_names[2]] = pygame.Rect(0, h_half, w_half, h_half)
            rects[track_names[3]] = pygame.Rect(w_half, h_half, w_half, h_half)
            
            # The Center Focus (Track 4)
            # Size: 50% of screen width/height?
            cw, ch = int(self.width * 0.5), int(self.height * 0.5)
            cx, cy = (self.width - cw) // 2, (self.height - ch) // 2
            rects[track_names[4]] = pygame.Rect(cx, cy, cw, ch)
        else:
            # Fallback for other counts: just stack horizontally
            w = self.width // num_tracks
            for i, name in enumerate(track_names):
                rects[name] = pygame.Rect(i * w, 0, w, self.height)
                
        return rects

    def render_frame(self, surface, audio_time, dt=0.016):
        """Draws a single frame to the provided surface."""
        surface.fill(Config.COLOR_BG)
        
        for name, rect in self.rects.items():
            track = self.tracks_data[name]
            state = self.render_state[name]
            
            # Subsurface for clipping
            # Clip rect to screen bounds to prevent crash if layout is slightly off
            safe_rect = rect.clip(surface.get_rect())
            if safe_rect.width <= 0 or safe_rect.height <= 0:
                continue
                
            sub = surface.subsurface(safe_rect)
            
            # Draw Viewport Content (Background + World)
            self._draw_viewport(sub, safe_rect, track, state, audio_time, dt)
            
            # Draw Border
            pygame.draw.rect(surface, Config.COLOR_SQUARE_BORDER, safe_rect, 2)
            
        # Draw UI Overlay (Global)
        if Config.ENABLE_UI:
            # Progress Bar
            bar_height = 6
            progress = min(1.0, audio_time / self.duration) if self.duration > 0 else 0
            pygame.draw.rect(surface, (30, 30, 30), (0, self.height - bar_height, self.width, bar_height))
            pygame.draw.rect(surface, (100, 200, 255), (0, self.height - bar_height, self.width * progress, bar_height))
            
            # Text
            time_str = f"{int(audio_time // 60)}:{int(audio_time % 60):02d} / {int(self.duration // 60)}:{int(self.duration % 60):02d}"
            txt = self.font.render(time_str, True, (200, 200, 200))
            surface.blit(txt, (10, self.height - bar_height - 20))

    def _draw_viewport(self, surface, rect, track, state, audio_time, dt=0.016):
        # --- 1. DRAW BACKGROUND ---
        bg_color = list(Config.COLOR_BG)
        
        # Dynamic Pulse
        if Config.ENABLE_DYNAMIC_BG and Config.ENABLE_SHAKE:
            # Brighten BG based on shake (proxy for intensity)
            pulse = min(Config.BG_PULSE_AMT, state["shake"] * Config.BG_PULSE_AMT)
            bg_color = (min(255, bg_color[0]+pulse), min(255, bg_color[1]+pulse), min(255, bg_color[2]+pulse))
            
        surface.fill(bg_color)
        
        # Draw Stars
        if Config.ENABLE_DYNAMIC_BG:
            w, h = rect.width, rect.height
            for star in state["stars"]:
                sx = int(star[0] * w)
                sy = int(star[1] * h)
                c = int(100 + pulse * 10) # Stars pulse slightly too
                pygame.draw.circle(surface, (c, c, c), (sx, sy), star[2])

        timeline = track["timeline"]
        if not timeline: return
        
        center = np.array([rect.width/2, rect.height/2])
        idx = np.searchsorted(track['onsets'], audio_time) - 1
        if idx < 0: idx = 0
        
        # --- SHAKE & PARTICLES UPDATE ---
        
        # Decay shake
        if Config.ENABLE_SHAKE:
            state["shake"] = max(0, state["shake"] - Config.SHAKE_DECAY * dt)
            
        # Update particles
        if Config.ENABLE_PARTICLES:
            alive_particles = []
            for p in state["particles"]:
                # p = [pos, vel, life, color]
                p[0] += p[1] * dt # Move
                p[2] -= Config.PARTICLE_DECAY * dt # Decay life
                if p[2] > 0:
                    alive_particles.append(p)
            state["particles"] = alive_particles

        # --- CAMERA ---

        target_cam = state["cam"]
        sq_world = np.array([0.0, 0.0]) # Default
        velocity = np.array([0.0, 0.0])
        
        if 0 <= idx < len(timeline):
            seg = timeline[idx]
            duration = seg['t1'] - seg['t0']
            progress = (audio_time - seg['t0']) / duration if duration > 0 else 0
            sq_world = seg['p0'] + (seg['p1'] - seg['p0']) * progress
            
            # Calculate Velocity for Cinema Lookahead
            velocity = (seg['p1'] - seg['p0']) / duration if duration > 0 else np.array([0.0, 0.0])
            
            # Cinema Camera Logic
            lookahead = np.array([0.0, 0.0])
            if Config.ENABLE_CINEMA_CAM:
                # Look ahead in direction of movement
                # We want the square to be 'pushed' back, so we move camera 'forward'
                lookahead = -velocity * Config.CAM_LOOKAHEAD
                
            target_cam = center - sq_world + lookahead
            
            # CHECK HIT (Trigger Effects)
            # Only trigger if progress is near end AND we haven't triggered this index yet
            if progress > Config.SHAKE_THRESHOLD and idx != state["last_hit_idx"]:
                state["last_hit_idx"] = idx
                
                # Add Shake
                if Config.ENABLE_SHAKE:
                    state["shake"] = min(1.0, state["shake"] + 0.6)
                
                # Spawn Particles
                if Config.ENABLE_PARTICLES:
                    hit_pos = seg['p1']
                    for _ in range(Config.PARTICLE_COUNT):
                        angle = random.uniform(0, 2*math.pi)
                        speed = random.uniform(50, Config.PARTICLE_SPEED)
                        vel = np.array([math.cos(angle)*speed, math.sin(angle)*speed])
                        state["particles"].append([hit_pos.copy(), vel, 1.0, track["color"]])

        # Smooth camera
        state["cam"] += (target_cam - state["cam"]) * Config.LERP_FACTOR
        
        # Apply Shake Offset to Camera
        final_cam = state["cam"].copy()
        if Config.ENABLE_SHAKE and state["shake"] > 0:
            shake_amt = state["shake"] * state["shake"] * Config.SHAKE_INTENSITY
            offset = np.array([
                random.uniform(-shake_amt, shake_amt),
                random.uniform(-shake_amt, shake_amt)
            ])
            final_cam += offset
    # --- DRAWING ---
    
        # 1. Update & Draw Trail
        if Config.ENABLE_TRAILS and 0 <= idx < len(timeline):
            # Add current pos
            state["trail"].append(sq_world.copy())
            if len(state["trail"]) > Config.TRAIL_LENGTH:
                state["trail"].pop(0)
                
            # Draw trail
            if len(state["trail"]) > 1:
                # We need points in screen space
                screen_points = [p + final_cam for p in state["trail"]]
                pygame.draw.lines(surface, track["color"], False, screen_points, 3)

        # 2. Draw Walls
        draw_range_start = max(0, idx - 5)
        draw_range_end = min(len(timeline), idx + 15)
        
        for i in range(draw_range_start, draw_range_end):
            item = timeline[i]
            p1 = item['w1'] + final_cam
            p2 = item['w2'] + final_cam
            
            is_active = (i == idx)
            if is_active and 0 <= idx < len(timeline):
                seg = timeline[idx]
                dur = seg['t1'] - seg['t0']
                prog = (audio_time - seg['t0']) / dur if dur > 0 else 0
                if prog > Config.SHAKE_THRESHOLD: 
                    col, w = (255, 255, 255), 12
                else:
                    col, w = track["color"], 7
            elif i < idx:
                col, w = (40, 42, 50), 2 
            else:
                c = track["color"]
                col, w = (c[0]//2, c[1]//2, c[2]//2), 4
            
            # Glow Effect (Cheap)
            if Config.ENABLE_GLOW and is_active:
                # Draw a wider, darker line underneath
                glow_col = (max(0, col[0]-100), max(0, col[1]-100), max(0, col[2]-100))
                pygame.draw.line(surface, glow_col, p1, p2, w + 6)
            
            pygame.draw.line(surface, col, p1, p2, w)
            
        # 3. Draw Square
        if 0 <= idx < len(timeline):
            sq_pos = sq_world + final_cam
            sz = Config.SQUARE_SIZE
            # Draw glow for square
            if Config.ENABLE_GLOW:
                pygame.draw.rect(surface, (100, 100, 100), 
                                (sq_pos[0]-(sz+6)/2, sq_pos[1]-(sz+6)/2, sz+6, sz+6))
                                
            pygame.draw.rect(surface, Config.COLOR_SQUARE, 
                             (sq_pos[0]-sz/2, sq_pos[1]-sz/2, sz, sz))
                             
        # 4. Draw Particles
        if Config.ENABLE_PARTICLES:
            for p in state["particles"]:
                # p = [pos, vel, life, color]
                pos = p[0] + final_cam
                life = p[2]
                # Fade alpha... Pygame draws with color. 
                # We can simulate fade by shrinking or darkening.
                # Darkening:
                base_col = p[3]
                col = (int(base_col[0]*life), int(base_col[1]*life), int(base_col[2]*life))
                sz = max(1, int(Config.PARTICLE_SIZE * life))
                
                pygame.draw.rect(surface, col, (pos[0], pos[1], sz, sz))


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
            
            # Update screen surface
                    screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
            
            dt = clock.get_time() / 1000.0
            self.render_frame(screen, audio_time, dt)
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
            self.render_frame(screen, audio_time, dt)
            
            fname = os.path.join(output_dir, f"frame_{i:05d}.png")
            pygame.image.save(screen, fname)
            
            if i % 100 == 0:
                print(f"Rendered {i}/{total_frames} frames ({i/total_frames*100:.1f}%)", end='\r')
                
        print("\nRendering complete.")
        pygame.quit()
