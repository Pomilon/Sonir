import pygame
import random
import time
import numpy as np
from .renderer import SonirRenderer
from .config import Config

class RhythmGame(SonirRenderer):
    def __init__(self, tracks_data, audio_path, modifiers=None, autoplay=False):
        # Initialize Game State needed for layout calculation BEFORE super().__init__
        self.track_slot_map = {} 
        self.slots = []
        self.track_keys = {}
        self.key_map = {}
        
        # Setup initial sequential mapping
        sorted_names = list(tracks_data.keys())
        for i, name in enumerate(sorted_names):
            self.track_slot_map[name] = i
            
        super().__init__(tracks_data, audio_path)
        
        self.autoplay = autoplay
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.health = 100.0
        self.max_health = 100.0
        self.game_over = False
        
        # Countdown State
        self.in_countdown = True
        self.countdown_start = time.time()
        self.countdown_duration = 3.0
        
        # Scoring Windows
        self.PERFECT = 0.04
        self.GOOD = 0.10
        self.BAD = 0.18
        
        # State
        self.last_feedback = ""
        self.last_feedback_time = 0
        self.feedback_color = (255, 255, 255)
        self.processed_onsets = {name: set() for name in tracks_data.keys()}
        self.track_indices = {name: 0 for name in tracks_data.keys()}
        self.modifiers = modifiers if modifiers else []
        
        # --- Chaos / Layout Management ---
        # Helper to get default keys for slot index
        def get_keys_for_slot(i, total):
            if total == 1: return [pygame.K_SPACE, pygame.K_f, pygame.K_j]
            if total == 2: return [[pygame.K_d, pygame.K_LEFT], [pygame.K_k, pygame.K_RIGHT]][i]
            if total == 3: return [[pygame.K_d], [pygame.K_f], [pygame.K_j]][i]
            if total == 4: return [[pygame.K_d], [pygame.K_f], [pygame.K_j], [pygame.K_k]][i]
            if total == 5: return [[pygame.K_s], [pygame.K_d], [pygame.K_SPACE], [pygame.K_j], [pygame.K_k]][i]
            return []

        # Build Slots (Logical definitions)
        for i in range(len(sorted_names)):
            self.slots.append({
                "id": i,
                "keys": get_keys_for_slot(i, len(sorted_names))
            })
            
        # Build initial key map
        self._update_key_map()
        
        # Modifier Timers
        self.chaos_timer = time.time() + 8.0 # Give a bit more time at start
        self.focus_mode = "all" 
        self.focus_timer = 0
        self.focus_duration = 5.0 
        
        if "focus" in self.modifiers:
            self.focus_mode = random.choice(sorted_names)
            self.focus_timer = time.time() + self.focus_duration

    def _calculate_layout(self, num_tracks):
        # Override to support shuffling
        # 1. Get standard layout rects (as a list of Rects) based on current size
        standard_rects = []
        
        # We reuse the logic from base, but apply it to indices
        if num_tracks == 1:
            standard_rects = [pygame.Rect(0, 0, self.width, self.height)]
        elif num_tracks == 2:
            h = self.height // 2
            standard_rects = [
                pygame.Rect(0, 0, self.width, h),
                pygame.Rect(0, h, self.width, h)
            ]
        elif num_tracks == 4:
            w, h = self.width // 2, self.height // 2
            standard_rects = [
                pygame.Rect(0, 0, w, h),
                pygame.Rect(0, h, w, h),
                pygame.Rect(w, 0, w, h),
                pygame.Rect(w, h, w, h)
            ]
        elif num_tracks == 5:
            w_half, h_half = self.width // 2, self.height // 2
            cw, ch = int(self.width * 0.5), int(self.height * 0.5)
            cx, cy = (self.width - cw) // 2, (self.height - ch) // 2
            standard_rects = [
                pygame.Rect(0, 0, w_half, h_half),
                pygame.Rect(w_half, 0, w_half, h_half),
                pygame.Rect(0, h_half, w_half, h_half),
                pygame.Rect(w_half, h_half, w_half, h_half),
                pygame.Rect(cx, cy, cw, ch)
            ]
        else:
            if num_tracks > 0:
                w = self.width // num_tracks
                standard_rects = [pygame.Rect(i * w, 0, w, self.height) for i in range(num_tracks)]

        # 2. Map Rects to Tracks using track_slot_map
        final_rects = {}
        # If map not ready (during super init), assume default order
        if not hasattr(self, 'track_slot_map') or not self.track_slot_map:
            names = list(self.tracks_data.keys())
            for i, name in enumerate(names):
                final_rects[name] = standard_rects[i] if i < len(standard_rects) else pygame.Rect(0,0,0,0)
        else:
            for name, slot_idx in self.track_slot_map.items():
                if slot_idx < len(standard_rects):
                    final_rects[name] = standard_rects[slot_idx]
        
        return final_rects

    def _update_key_map(self):
        """Rebuilds self.key_map based on current track->slot assignment."""
        self.key_map = {}
        
        # Map Track -> Keys
        self.track_keys = {}
        for track_name, slot_idx in self.track_slot_map.items():
            keys = self.slots[slot_idx]["keys"]
            self.track_keys[track_name] = keys
            
            for k in keys:
                if k not in self.key_map: self.key_map[k] = []
                self.key_map[k].append(track_name)
                
        # Trigger layout update to reflect new positions
        self.rects = self._calculate_layout(len(self.tracks_data))

    def _handle_input(self, events, audio_time, paused):
        running, new_paused, offset_change = super()._handle_input(events, audio_time, paused, handle_pause=False)
        
        # --- Countdown Logic ---
        if self.in_countdown:
            # Allow quitting during countdown
            for event in events:
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    return False, True, 0
            
            elapsed = time.time() - self.countdown_start
            if elapsed < self.countdown_duration:
                return True, True, 0 
            else:
                self.in_countdown = False
                new_paused = False 
        
        if offset_change != 0 and offset_change != -999999:
            offset_change = 0
            
        if self.game_over:
            new_paused = True 
            for event in events:
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    return False, True, 0
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    # Restart
                    self.health = self.max_health
                    self.score = 0
                    self.combo = 0
                    self.game_over = False
                    self.in_countdown = True
                    self.countdown_start = time.time()
                    self.processed_onsets = {name: set() for name in self.tracks_data.keys()}
                    self.track_indices = {name: 0 for name in self.tracks_data.keys()}
                    return True, True, -999999 
            return True, True, 0

        if not new_paused and running and not self.game_over:
            if self.health <= 0:
                self.game_over = True
                self.health = 0
                return True, True, 0

            self.health = max(0, self.health - (5.0 * 0.016))
            
            # --- Autoplay Logic ---
            if self.autoplay:
                for name, track in self.tracks_data.items():
                    onsets = track['onsets']
                    idx = np.searchsorted(onsets, audio_time)
                    if idx < len(onsets):
                        note_time = onsets[idx]
                        if abs(note_time - audio_time) < self.PERFECT:
                            if note_time not in self.processed_onsets[name]:
                                self._process_hit(name, audio_time)

            # Miss Detection
            for name in list(self.track_indices.keys()):
                onsets = self.tracks_data[name]['onsets']
                while self.track_indices[name] < len(onsets):
                    curr_idx = self.track_indices[name]
                    note_time = onsets[curr_idx]
                    
                    if audio_time > note_time + self.BAD:
                        if note_time not in self.processed_onsets[name]:
                            self._trigger_miss(name)
                            self.processed_onsets[name].add(note_time)
                        self.track_indices[name] += 1
                    else:
                        break

            # --- Modifiers ---
            if "chaos" in self.modifiers:
                if time.time() > self.chaos_timer:
                    track_names = list(self.tracks_data.keys())
                    slot_indices = list(range(len(self.slots)))
                    
                    # Force a change in layout
                    # Get current assignments
                    current_assignment = [self.track_slot_map[name] for name in track_names]
                    
                    # Shuffle until different
                    if len(slot_indices) > 1:
                        while True:
                            random.shuffle(slot_indices)
                            if slot_indices != current_assignment:
                                break
                    
                    for i, name in enumerate(track_names):
                        self.track_slot_map[name] = slot_indices[i]
                        
                    self._update_key_map()
                    self.chaos_timer = time.time() + 8.0 # Slower shuffle (8s) for fairness
                    self.last_feedback = "SHUFFLE!"
                    self.last_feedback_time = time.time()
                    self.feedback_color = (255, 0, 255)

            if "focus" in self.modifiers:
                if time.time() > self.focus_timer:
                    all_tracks = list(self.tracks_data.keys())
                    options = [t for t in all_tracks if t != self.focus_mode]
                    if options:
                        self.focus_mode = random.choice(options)
                    self.focus_timer = time.time() + self.focus_duration
                    self.last_feedback = "SWITCH!"
                    self.last_feedback_time = time.time()
                    self.feedback_color = (255, 255, 0)
            
            # Input
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key in self.key_map:
                        target_tracks = self.key_map[event.key]
                        for track_name in target_tracks:
                            if "focus" in self.modifiers and self.focus_mode != "all":
                                if track_name != self.focus_mode: continue
                            self._process_hit(track_name, audio_time)

        return running, new_paused, offset_change

    def _trigger_miss(self, track_name):
        loss = 100.0 if "death" in self.modifiers else 10.0
        self.health = max(0, self.health - loss)
        self.combo = 0
        self.last_feedback = "MISS"
        self.last_feedback_time = time.time()
        self.feedback_color = (255, 50, 50)

    def _process_hit(self, track_name, audio_time):
        track = self.tracks_data[track_name]
        onsets = track['onsets']
        idx = np.searchsorted(onsets, audio_time)
        
        candidates = []
        if idx < len(onsets): candidates.append(onsets[idx])
        if idx > 0: candidates.append(onsets[idx-1])
        if not candidates: return
        
        valid_candidates = [c for c in candidates if c not in self.processed_onsets[track_name]]
        
        if not valid_candidates:
            loss = 100.0 if "death" in self.modifiers else 4.0
            self.health = max(0, self.health - loss)
            self.combo = 0
            self.last_feedback = "X"
            self.last_feedback_time = time.time()
            self.feedback_color = (255, 50, 50)
            return
            
        closest_time = min(valid_candidates, key=lambda x: abs(x - audio_time))
        diff = abs(closest_time - audio_time)

        if diff < self.BAD:
            score_add = 0
            feedback = ""
            col = (255, 255, 255)
            
            if diff < self.PERFECT:
                score_add = 300
                feedback = "PERFECT"
                col = (100, 255, 255)
                self.health = min(self.max_health, self.health + 6.0)
            elif diff < self.GOOD:
                score_add = 100
                feedback = "GOOD"
                col = (100, 255, 100)
                self.health = min(self.max_health, self.health + 3.0)
            else:
                score_add = 50
                feedback = "OK"
                col = (200, 200, 100)
                self.health = min(self.max_health, self.health + 0.5)
            
            self.score += score_add
            self.combo += 1
            if self.combo > self.max_combo: self.max_combo = self.combo
            
            self.last_feedback = feedback
            self.last_feedback_time = time.time()
            self.feedback_color = col
            self.processed_onsets[track_name].add(closest_time)
        else:
            loss = 100.0 if "death" in self.modifiers else 4.0
            self.health = max(0, self.health - loss)
            self.combo = 0
            self.last_feedback = "X" 
            self.last_feedback_time = time.time()
            self.feedback_color = (255, 50, 50)

    def _draw_overlay(self, surface):
        if not self.font: return
        w, h = surface.get_size()
        
        # Countdown Overlay
        if self.in_countdown:
            remaining = int(self.countdown_duration - (time.time() - self.countdown_start)) + 1
            # Simple scaling for "pulse" effect
            scale = 1.0 + (time.time() % 0.5) * 0.2
            
            base_size = 120
            final_size = int(base_size * scale)
            # Use default font
            big_font = pygame.font.Font(None, final_size)
            
            txt = big_font.render(str(remaining), True, (255, 255, 255))
            r = txt.get_rect(center=(w/2, h/2))
            surface.blit(txt, r)
            return

        if self.game_over:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            s.fill((0, 0, 0, 180))
            surface.blit(s, (0,0))
            
            go_font = pygame.font.Font(None, 80)
            go_txt = go_font.render("GAME OVER", True, (255, 50, 50))
            go_rect = go_txt.get_rect(center=(w/2, h/2 - 50))
            surface.blit(go_txt, go_rect)
            
            score_txt = self.font.render(f"Final Score: {self.score}", True, (255, 255, 255))
            score_rect = score_txt.get_rect(center=(w/2, h/2 + 20))
            surface.blit(score_txt, score_rect)
            
            rst_txt = self.font.render("Press 'R' to Retry", True, (200, 200, 200))
            rst_rect = rst_txt.get_rect(center=(w/2, h/2 + 60))
            surface.blit(rst_txt, rst_rect)
            return

        # Score & Combo
        score_txt = self.font.render(f"Score: {self.score}", True, (255, 255, 255))
        surface.blit(score_txt, (20, 20))
        
        if self.combo > 0:
            combo_txt = self.font.render(f"{self.combo}x", True, (100, 200, 255))
            combo_rect = combo_txt.get_rect(bottomleft=(20, h - 50))
            surface.blit(combo_txt, combo_rect)
            
        # Health Bar
        pygame.draw.rect(surface, (50, 0, 0), (w - 220, 20, 200, 20))
        pct = max(0, self.health / self.max_health)
        col = (255, 50, 50) if pct < 0.2 else (100, 255, 100) if pct > 0.5 else (255, 255, 50)
        pygame.draw.rect(surface, col, (w - 220, 20, 200 * pct, 20))
        pygame.draw.rect(surface, (255, 255, 255), (w - 220, 20, 200, 20), 2)
        
        if "death" in self.modifiers:
            d_txt = self.font.render("SUDDEN DEATH", True, (255, 0, 0))
            surface.blit(d_txt, (w - 220, 45))
        
        # Chaos Timer Overlay (Side position, no flash)
        if "chaos" in self.modifiers:
            time_left = self.chaos_timer - time.time()
            if time_left < 3.0 and not self.game_over:
                secs = int(time_left) + 1
                # Use default font, larger size
                c_font = pygame.font.Font(None, 48)
                
                txt = c_font.render(f"SHUFFLE: {secs}", True, (255, 255, 255))
                # Position top-leftish, under score
                surface.blit(txt, (20, 60))
        
        # Feedback
        if self.last_feedback and time.time() - self.last_feedback_time < 0.3: 
            fb_surf = self.font.render(self.last_feedback, True, self.feedback_color)
            r = fb_surf.get_rect(center=(w//2, h//2 + 50)) # Move down slightly to not overlap chaos timer
            surface.blit(fb_surf, r)
            
        # Focus Indicator
        if "focus" in self.modifiers and self.focus_mode != "all":
            if self.focus_mode in self.rects:
                r = self.rects[self.focus_mode]
                pygame.draw.rect(surface, (255, 255, 0), r, 4)
                remaining = max(0, self.focus_timer - time.time())
                t_txt = self.font.render(f"{remaining:.1f}", True, (255, 255, 0))
                tr = t_txt.get_rect(bottomleft=(r.x + 10, r.bottom - 10))
                surface.blit(t_txt, tr)

        # Controls Hints
        for slot in self.slots:
            assigned_track = None
            for name, s_idx in self.track_slot_map.items():
                if s_idx == slot["id"]:
                    assigned_track = name
                    break
            
            if not assigned_track: continue
            
            rect = self.rects[assigned_track]
            keys = slot["keys"]
            key_names = [pygame.key.name(k).upper() for k in keys]
            hint = "/".join(key_names)
            
            # Simple Grey Hint
            col = (200, 200, 200)
            txt = self.font.render(f"[{hint}]", True, col)
            tr = txt.get_rect(center=(rect.centerx, rect.bottom - 20))
            surface.blit(txt, tr)
            
            n_txt = self.font.render(assigned_track.upper(), True, (100, 100, 100))
            nr = n_txt.get_rect(midbottom=(tr.centerx, tr.top - 5))
            surface.blit(n_txt, nr)
