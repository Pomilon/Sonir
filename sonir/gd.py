import numpy as np
import pygame
import random
import math
from .renderer import SonirRenderer
from .config import Config

class PlayerMode:
    CUBE = 0
    SHIP = 1
    BALL = 2

class GeometryDashGame(SonirRenderer):
    def __init__(self, tracks_data, audio_path, autoplay=False):
        super().__init__(tracks_data, audio_path)
        self.autoplay = autoplay
        
        # Physics Constants
        self.GRAVITY = 2500.0
        self.JUMP_FORCE = -780.0
        
        # Ship Physics
        self.SHIP_GRAVITY = 1000.0
        self.SHIP_LIFT = -1100.0
        self.SHIP_TERMINAL_VEL = 600.0
        
        self.SCROLL_SPEED = 600.0 
        self.GROUND_Y = Config.HEIGHT - 100
        self.CEILING_Y = 100
        
        # Level Data
        self.segments = [] 
        self.obstacles = []
        self.portals = [] 
        self.orbs = [] # Jump Rings
        
        # Player State
        self.mode = PlayerMode.CUBE
        self.player_pos = np.array([200.0, self.GROUND_Y])
        self.player_vel = np.array([0.0, 0.0])
        self.is_grounded = True
        self.rotation = 0.0
        self.dead = False
        self.holding_jump = False
        self.gravity_flip = 1.0 # 1.0 or -1.0
        
        # Visuals
        self.shake = 0.0
        self.particles = []
        self.bg_color = [20, 20, 30]
        
        # Init
        self._generate_level()
        
        # Force start mode based on first segment
        if self.segments:
            self.mode = self.segments[0]["mode"]
            
        # Fonts
        try:
            self.font_large = pygame.font.Font(None, 64)
            self.font_small = pygame.font.Font(None, 24)
        except:
            self.font_large = None
            self.font_small = None

    def _generate_level(self):
        # 1. Analyze Density to create Segments
        all_onsets = []
        for name, data in self.tracks_data.items():
            for onset in data['onsets']:
                all_onsets.append(onset)
        all_onsets.sort()
        
        if not all_onsets: return

        # Density analysis
        duration = self.duration
        window_size = 3.0
        current_time = 0
        
        current_mode = PlayerMode.CUBE
        current_speed = 1.0
        
        # Force start with Cube for 5 seconds
        self.segments.append({
            "start": 0.0,
            "mode": PlayerMode.CUBE,
            "speed": 1.0
        })
        current_time = 5.0
        
        while current_time < duration:
            count = 0
            for t in all_onsets:
                if current_time <= t < current_time + window_size:
                    count += 1
            
            density = count / window_size
            
            # Mode Switching Logic
            if density > 5.0: # Extreme
                next_mode = PlayerMode.SHIP
                current_speed = 1.2
            elif density > 2.5 and density <= 5.0: # Moderate
                # Random chance for Ball if we have enough segments
                next_mode = PlayerMode.BALL if random.random() > 0.5 else PlayerMode.CUBE
                current_speed = 1.0
            else: # Chill
                next_mode = PlayerMode.CUBE
                current_speed = 0.9
                
            # Cooldown: Don't switch if we just switched? 
            # Simplified: just append if changed, otherwise extend
            if self.segments[-1]["mode"] != next_mode:
                self.segments.append({
                    "start": current_time, 
                    "mode": next_mode, 
                    "speed": current_speed
                })
            
            current_time += window_size
            
        # 2. Place Obstacles
        last_x = 0
        for t in all_onsets:
            x = self._get_x_for_time(t)
            
            # Distance check
            if x - last_x < 250 * self._get_speed_at(t): continue
            
            mode = self._get_mode_at(t)
            
            if mode == PlayerMode.SHIP:
                # Pillars
                gap = 250
                center_y = random.uniform(self.CEILING_Y + 100, self.GROUND_Y - 100)
                
                self.obstacles.append({
                    "type": "block",
                    "rect": pygame.Rect(x, center_y + gap/2, 60, self.GROUND_Y - (center_y + gap/2)),
                    "color": (0, 200, 255)
                })
                self.obstacles.append({
                    "type": "block",
                    "rect": pygame.Rect(x, self.CEILING_Y, 60, (center_y - gap/2) - self.CEILING_Y),
                    "color": (0, 200, 255)
                })
                
            elif mode == PlayerMode.BALL:
                # Ball Gameplay: Switch gravity to avoid spikes/blocks
                # We place alternating obstacles on floor/ceiling
                side = random.choice([1, -1]) # 1 = Floor, -1 = Ceiling
                
                y = self.GROUND_Y - 40 if side == 1 else self.CEILING_Y
                obs_type = "spike"
                
                # Ball Spike
                h = 40
                r_y = self.GROUND_Y - h if side == 1 else self.CEILING_Y
                
                self.obstacles.append({
                    "type": "spike",
                    "rect": pygame.Rect(x, r_y, 40, 40),
                    "color": (255, 50, 50),
                    "flipped": (side == -1)
                })
                
            else: # CUBE
                # Yellow Orb Chance
                if random.random() > 0.8:
                    # Place Orb
                    y = self.GROUND_Y - 120
                    self.orbs.append({
                        "rect": pygame.Rect(x, y, 40, 40),
                        "active": True
                    })
                    # Place spike under orb to force usage
                    self.obstacles.append({
                        "type": "spike",
                        "rect": pygame.Rect(x, self.GROUND_Y - 40, 40, 40),
                        "color": (255, 0, 0)
                    })
                else:
                    # Standard Spike/Block
                    obs_type = random.choice(["spike", "block"])
                    if obs_type == "spike":
                        self.obstacles.append({
                            "type": "spike",
                            "rect": pygame.Rect(x, self.GROUND_Y - 40, 40, 40),
                            "color": (255, 50, 50)
                        })
                    else:
                        self.obstacles.append({
                            "type": "block",
                            "rect": pygame.Rect(x, self.GROUND_Y - 60, 50, 60),
                            "color": (0, 255, 255)
                        })
            
            last_x = x
            
        # 3. Portals
        for seg in self.segments:
            if seg["start"] <= 0.1: continue
            x = self._get_x_for_time(seg["start"])
            
            p_type = seg["mode"]
            # Colors: Cube=Green, Ship=Pink, Ball=Orange
            col = (100, 255, 100) 
            if p_type == PlayerMode.SHIP: col = (255, 100, 200)
            elif p_type == PlayerMode.BALL: col = (255, 150, 50)
            
            self.portals.append({
                "rect": pygame.Rect(x, self.GROUND_Y - 150, 50, 100),
                "type": p_type,
                "color": col
            })

    def _get_x_for_time(self, t):
        # Accurate X integration
        x = 200 # Player Offset
        if not self.segments: return x + t * self.SCROLL_SPEED
        
        for i, seg in enumerate(self.segments):
            next_start = self.segments[i+1]["start"] if i+1 < len(self.segments) else 999999
            
            seg_dur = min(t, next_start) - max(0, seg["start"])
            if seg_dur > 0:
                x += seg_dur * (seg["speed"] * self.SCROLL_SPEED)
                
            if t < next_start: break
        return x

    def _get_speed_at(self, t):
        for seg in reversed(self.segments):
            if t >= seg["start"]: return seg["speed"]
        return 1.0

    def _get_mode_at(self, t):
        for seg in reversed(self.segments):
            if t >= seg["start"]: return seg["mode"]
        return PlayerMode.CUBE

    def _spawn_particles(self, pos, count=10, color=(255, 255, 255)):
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(50, 300)
            vel = np.array([math.cos(angle)*speed, math.sin(angle)*speed])
            self.particles.append([np.array(pos, dtype=float), vel, 1.0, color])

    def _handle_input(self, events, audio_time, paused):
        running, new_paused, offset_change = super()._handle_input(events, audio_time, paused, handle_pause=False)
        
        self.holding_jump = False
        keys = pygame.key.get_pressed()
        mouse = pygame.mouse.get_pressed()
        if keys[pygame.K_SPACE] or keys[pygame.K_UP] or mouse[0]:
            self.holding_jump = True
        
        if not new_paused and running and not self.dead:
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key in [pygame.K_SPACE, pygame.K_UP]:
                        self._attempt_jump()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._attempt_jump()
                        
        if self.dead and keys[pygame.K_r]:
             self._reset_level()
             return True, True, -999999

        return running, new_paused, offset_change

    def _attempt_jump(self):
        p_rect = pygame.Rect(self.player_pos[0], self.player_pos[1]-40, 40, 40)
        pass # Handle inside Update loop for frame perfect sync

    def _reset_level(self):
        self.player_pos = np.array([200.0, self.GROUND_Y])
        self.player_vel = np.array([0.0, 0.0])
        self.dead = False
        self.rotation = 0.0
        self.mode = self.segments[0]["mode"] if self.segments else PlayerMode.CUBE
        self.gravity_flip = 1.0
        self.is_grounded = True

    def render_frame(self, surface, audio_time, dt=0.016):
        world_x = -self._get_x_for_time(audio_time) + 200
        
        # 1. Input Logic (Frame Perfect)
        just_jumped = False
        if self.holding_jump and not self.dead:
            if self.mode == PlayerMode.CUBE:
                if self.is_grounded:
                    self.player_vel[1] = self.JUMP_FORCE * self.gravity_flip
                    self.is_grounded = False
                    just_jumped = True
            elif self.mode == PlayerMode.BALL:
                # Ball flips on click/tap (handled in event loop, but we need debounce)
                # Ball doesn't hold-jump usually. It's toggle.
                pass
        
        # Actually, let's move physics updates here.
        if not self.dead:
            # --- Check Portals ---
            p_rect = pygame.Rect(self.player_pos[0], self.player_pos[1]-40, 40, 40)
            for p in self.portals:
                sr = p["rect"].move(world_x, 0)
                if p_rect.colliderect(sr):
                    if self.mode != p["type"]:
                        self.mode = p["type"]
                        # Reset physics slightly on mode switch
                        self.player_vel[1] = 0
                        self.gravity_flip = 1.0
                        if self.mode == PlayerMode.SHIP: self.rotation = 0
            
            # --- Check Orbs (Yellow Rings) ---
            # Hit if holding jump within range
            hit_orb = False
            if self.holding_jump and self.mode == PlayerMode.CUBE:
                for orb in self.orbs:
                    sr = orb["rect"].move(world_x, 0)
                    if p_rect.colliderect(sr):
                        # Bounce!
                        self.player_vel[1] = self.JUMP_FORCE * 1.2 * self.gravity_flip
                        self.is_grounded = False
                        self._spawn_particles(self.player_pos, 5, (255, 255, 50))
                        hit_orb = True
                        break # One orb at a time

            # --- Physics ---
            if self.mode == PlayerMode.CUBE:
                self.player_vel[1] += self.GRAVITY * dt * self.gravity_flip
                self.player_pos += self.player_vel * dt
                
                # Rotation
                if self.is_grounded:
                    # Snap to nearest 90
                    target = round(self.rotation / 90) * 90
                    self.rotation += (target - self.rotation) * 0.2
                else:
                    self.rotation -= 380 * dt * self.gravity_flip

            elif self.mode == PlayerMode.SHIP:
                if self.holding_jump or (self.autoplay and self._autoplay_ship(world_x)):
                    self.player_vel[1] += self.SHIP_LIFT * dt
                else:
                    self.player_vel[1] += self.SHIP_GRAVITY * dt
                
                # Terminal Velocity
                self.player_vel[1] = max(min(self.player_vel[1], 600), -600)
                self.player_pos += self.player_vel * dt
                
                # Tilt
                target_rot = -self.player_vel[1] * 0.1
                self.rotation += (target_rot - self.rotation) * 0.1

            elif self.mode == PlayerMode.BALL:
                pass # Logic in handle_input or specialized method?
                
                # Apply Gravity
                self.player_vel[1] += self.GRAVITY * dt * self.gravity_flip
                self.player_pos += self.player_vel * dt
                self.rotation += 200 * dt * self.gravity_flip

            # --- Collision / Ground ---
            floor_y = self.GROUND_Y
            ceil_y = self.CEILING_Y
            self.is_grounded = False # Assume air, prove ground
            
            p_rect = pygame.Rect(self.player_pos[0]+5, self.player_pos[1]-35, 30, 30) # Smaller hitbox
            
            # Floor/Ceiling
            if self.player_pos[1] >= floor_y:
                self.player_pos[1] = floor_y
                if self.mode != PlayerMode.SHIP: self.player_vel[1] = 0
                else: self.player_vel[1] = 0 # Ship slides
                self.is_grounded = True
                if self.gravity_flip == -1 and self.mode == PlayerMode.CUBE: self.dead = True # Cube die on wrong gravity floor? No
            
            if self.player_pos[1] <= ceil_y + 40: # Hit ceiling
                if self.mode == PlayerMode.SHIP:
                    self.player_pos[1] = ceil_y + 40
                    self.player_vel[1] = 0
                elif self.mode == PlayerMode.BALL and self.gravity_flip == -1:
                    self.player_pos[1] = ceil_y + 40
                    self.player_vel[1] = 0
                    self.is_grounded = True
            
            # Obstacles
            for obs in self.obstacles:
                sr = obs["rect"].move(world_x, 0)
                if sr.right < 0: continue
                if sr.left > self.width: break
                
                if p_rect.colliderect(sr):
                    # Resolve Collision
                    if obs["type"] == "spike":
                        self.dead = True
                    elif obs["type"] == "block":
                        # Determine side of collision
                        # If we were previously above, land.
                        # We need previous position? Approximation:
                        
                        # Check Y overlap
                        overlap_y = min(p_rect.bottom, sr.bottom) - max(p_rect.top, sr.top)
                        overlap_x = min(p_rect.right, sr.right) - max(p_rect.left, sr.left)
                        
                        if overlap_y < overlap_x and self.player_vel[1] > 0 and p_rect.bottom < sr.centery:
                            # Land on top
                            self.player_pos[1] = sr.top
                            self.player_vel[1] = 0
                            self.is_grounded = True
                        elif overlap_y < overlap_x and self.player_vel[1] < 0 and p_rect.top > sr.centery:
                            # Hit bottom (Ceiling bump)
                            self.player_pos[1] = sr.bottom + 40
                            self.player_vel[1] = 0
                            if self.gravity_flip == -1: self.is_grounded = True
                        else:
                            # Side hit = Death
                            self.dead = True

            # --- Autoplay (Cube/Ball) ---
            if self.autoplay and not self.dead:
                self._run_autoplay(world_x, p_rect)

        # 2. Draw
        self._draw_gd_scene(surface, world_x, dt)

    def _run_autoplay(self, world_x, p_rect):
        if self.mode == PlayerMode.CUBE:
            # Jump for spikes/blocks
            for obs in self.obstacles:
                sr = obs["rect"].move(world_x, 0)
                if sr.right < self.player_pos[0]: continue
                if sr.left > self.width: break
                
                dist = sr.left - p_rect.right
                if 0 < dist < 100 and self.is_grounded:
                    # Jump!
                    self.player_vel[1] = self.JUMP_FORCE * self.gravity_flip
                    self.is_grounded = False
                    
            # Use Orbs
            for orb in self.orbs:
                sr = orb["rect"].move(world_x, 0)
                if p_rect.colliderect(sr):
                     self.player_vel[1] = self.JUMP_FORCE * 1.2 * self.gravity_flip
                     
        elif self.mode == PlayerMode.BALL:
            # Flip to avoid obstacles
            # Check current path collision
            imminent_death = False
            for obs in self.obstacles:
                sr = obs["rect"].move(world_x, 0)
                if sr.right < self.player_pos[0]: continue
                if sr.left > self.width: break
                if 0 < sr.left - p_rect.right < 150:
                    # Check vertical alignment
                    if abs(sr.centery - self.player_pos[1]) < 50:
                        imminent_death = True
            
            if imminent_death and self.is_grounded:
                self.gravity_flip *= -1
                self.player_vel[1] = self.GRAVITY * 0.1 * self.gravity_flip # Push off

    def _autoplay_ship(self, world_x):
        # Target center of safe zone
        target_y = (self.GROUND_Y + self.CEILING_Y) / 2
        # Scan for blocks
        for obs in self.obstacles:
            sr = obs["rect"].move(world_x, 0)
            if sr.right < self.player_pos[0]: continue
            if sr.left > self.width: break
            
            if sr.left - self.player_pos[0] < 300:
                # Avoid this block
                if sr.centery > self.player_pos[1]: # Block is below
                    target_y = sr.top - 60
                else: # Block is above
                    target_y = sr.bottom + 60
                break
        
        # Simple P-Controller
        if self.player_pos[1] > target_y: return True
        return False

    def _draw_gd_scene(self, surface, world_x, dt):
        surface.fill((20, 20, 30))
        
        # Draw Floor/Ceiling
        pygame.draw.rect(surface, (50, 60, 80), (0, self.GROUND_Y, self.width, self.height))
        pygame.draw.rect(surface, (50, 60, 80), (0, 0, self.width, self.CEILING_Y))
        pygame.draw.line(surface, (100, 200, 255), (0, self.GROUND_Y), (self.width, self.GROUND_Y), 3)
        pygame.draw.line(surface, (100, 200, 255), (0, self.CEILING_Y), (self.width, self.CEILING_Y), 3)
        
        # Orbs
        for orb in self.orbs:
            sr = orb["rect"].move(world_x, 0)
            if 0 < sr.right and sr.left < self.width:
                pygame.draw.circle(surface, (255, 255, 0), sr.center, 20, 4)
                pygame.draw.circle(surface, (255, 255, 100), sr.center, 15)

        # Portals
        for p in self.portals:
            sr = p["rect"].move(world_x, 0)
            if 0 < sr.right and sr.left < self.width:
                pygame.draw.rect(surface, p["color"], sr, 5)
                
        # Obstacles
        for obs in self.obstacles:
            sr = obs["rect"].move(world_x, 0)
            if 0 < sr.right and sr.left < self.width:
                col = obs["color"]
                if obs["type"] == "spike":
                    pts = [sr.bottomleft, sr.midtop, sr.bottomright]
                    if obs.get("flipped"):
                        pts = [sr.topleft, sr.midbottom, sr.topright]
                    pygame.draw.polygon(surface, col, pts)
                    pygame.draw.polygon(surface, (255,255,255), pts, 2)
                else:
                    pygame.draw.rect(surface, col, sr)
                    pygame.draw.rect(surface, (255,255,255), sr, 2)

        # Player
        if not self.dead:
            sz = 40
            surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
            col = (255, 200, 50)
            if self.mode == PlayerMode.SHIP: col = (255, 100, 200)
            elif self.mode == PlayerMode.BALL: col = (255, 150, 50)
            
            surf.fill(col)
            pygame.draw.rect(surf, (255, 255, 255), (0,0,sz,sz), 3)
            
            # Rotation and Draw
            rot = pygame.transform.rotate(surf, self.rotation)
            r = rot.get_rect(center=(self.player_pos[0]+20, self.player_pos[1]-20))
            surface.blit(rot, r)

        # Game Over UI
        if self.dead and self.font_large:
            txt = self.font_large.render("CRASHED!", True, (255, 50, 50))
            surface.blit(txt, txt.get_rect(center=(self.width/2, self.height/2)))