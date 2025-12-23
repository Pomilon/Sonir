import numpy as np
import math
from .config import Config

class SonirCore:
    """
    The deterministic physics engine for Sonir.
    Handles the creation of the 2D world geometry based on timestamped events (onsets).
    """
    
    @staticmethod
    def bake(onsets, speed=Config.SQUARE_SPEED, seed=None):
        """
        Generates the wall geometry and flight path for a list of timestamps.
        
        Args:
            onsets (np.array): Sorted array of timestamps (seconds).
            speed (float): Speed of the square in units per second.
            seed (int): Optional seed for random number generation to ensure determinism.
            
        Returns:
            tuple: (timeline, onsets)
                timeline: A list of segment dictionaries containing positions and wall coordinates.
                onsets: The modified onsets array (guaranteed to start at 0.0) used for the timeline.
        """
        if len(onsets) == 0:
            return [], onsets
        
        # Initialize Random State
        rng = np.random.RandomState(seed)
            
        # Ensure we start at 0
        if onsets[0] > 0:
            onsets = np.insert(onsets, 0, 0.0)
            
        # Sanitize onsets: Remove duplicates and sort (though likely sorted)
        # We need strictly increasing values to avoid dt=0
        onsets = np.unique(onsets)
        
        timeline = []
        curr_p = np.array([0.0, 0.0])
        
        # Initial direction (randomized or fixed, let's keep it semi-random but consistent)
        curr_angle = rng.uniform(0, 2 * math.pi)
        curr_d = np.array([math.cos(curr_angle), math.sin(curr_angle)])
        
        for i in range(len(onsets) - 1):
            t0 = onsets[i]
            t1 = onsets[i+1]
            dt = t1 - t0
            
            # Calculate hit position
            hit_p = curr_p + curr_d * (speed * dt)
            
            # Turn logic (Reflection)
            # Using logic from source: 75 to 135 degrees turn
            turn = rng.uniform(math.radians(75), math.radians(135))
            if rng.random_sample() > 0.5: 
                turn *= -1
                
            new_angle = math.atan2(curr_d[1], curr_d[0]) + turn
            next_d = np.array([math.cos(new_angle), math.sin(new_angle)])
            
            # Wall orientation (Perpendicular to the bisector of the bounce)
            # Actually source does: norm = (curr_d - next_d)
            norm = (curr_d - next_d)
            norm_len = np.linalg.norm(norm)
            norm /= norm_len if norm_len > 0 else 1
            
            # Wall vector (perpendicular to normal)
            wdir = np.array([-norm[1], norm[0]])
            
            # Wall length factor (aesthetic)
            wall_len = 90
            
            timeline.append({
                't0': t0,
                't1': t1,
                'p0': curr_p.copy(),
                'p1': hit_p.copy(),
                'w1': hit_p + wdir * wall_len,
                'w2': hit_p - wdir * wall_len
            })
            
            curr_p, curr_d = hit_p, next_d
            
        return timeline, onsets
