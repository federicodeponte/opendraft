"""
ABOUTME: Decentralized backpressure signaling for rate limit coordination
ABOUTME: Uses Modal.Dict for cross-container state sharing across draft workers
"""

import time
import json
import logging
from enum import Enum
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# Pressure configuration - tune these based on observed behavior
PRESSURE_CONFIG = {
    "recovery_window_seconds": 60,    # Rolling window for 429 decay
    "429_count_critical": 25,         # Max before critical pressure
    "pause_threshold": 0.8,           # Pause spawning above this
    "resume_threshold": 0.5,          # Resume spawning below this
    "min_delay_seconds": 0.1,
    "max_delay_seconds": 5.0,
    "proxy_degraded_threshold": 5,    # 429s before proxy marked degraded
}


class APIType(Enum):
    """API types for rate limit tracking."""
    GEMINI_PRIMARY = "gemini_primary"
    GEMINI_FALLBACK = "gemini_fallback"
    GEMINI_FALLBACK_2 = "gemini_fallback_2"
    GEMINI_FALLBACK_3 = "gemini_fallback_3"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    CROSSREF = "crossref"
    WEB_SEARCH = "web_search"


# API types for rate limit tracking
GEMINI_API_TYPES = [
    APIType.GEMINI_PRIMARY,
    APIType.GEMINI_FALLBACK,
    APIType.GEMINI_FALLBACK_2,
    APIType.GEMINI_FALLBACK_3,
]


class BackpressureManager:
    """
    Manages rate limit backpressure across Modal containers via shared state.
    
    Uses Modal.Dict for cross-container coordination:
    - Workers signal 429 errors
    - Orchestrator reads pressure to adjust batch sizes
    - All containers share the same rate limit state
    """
    
    def __init__(self, dict_name: str = "draft-backpressure"):
        """
        Initialize backpressure manager.
        
        Args:
            dict_name: Name of Modal.Dict for shared state
        """
        self.dict_name = dict_name
        self._store = None
        self._local_cache = {}  # Local fallback for non-Modal environments
        self._is_modal = False
        
    def _get_store(self):
        """Lazy-load Modal.Dict to avoid import errors outside Modal."""
        if self._store is not None:
            return self._store
            
        try:
            import modal
            self._store = modal.Dict.from_name(self.dict_name, create_if_missing=True)
            self._is_modal = True
            logger.debug(f"Using Modal.Dict: {self.dict_name}")
        except Exception as e:
            logger.warning(f"Modal.Dict not available ({e}), using local cache")
            self._store = self._local_cache
            self._is_modal = False
            
        return self._store
    
    def _get(self, key: str, default=None):
        """Get value from store with fallback."""
        store = self._get_store()
        try:
            if self._is_modal:
                return store.get(key, default)
            else:
                return store.get(key, default)
        except Exception as e:
            logger.error(f"Failed to get {key}: {e}")
            return default
    
    def _put(self, key: str, value):
        """Put value in store."""
        store = self._get_store()
        try:
            if self._is_modal:
                store[key] = value
            else:
                store[key] = value
        except Exception as e:
            logger.error(f"Failed to put {key}: {e}")
    
    def signal_429(self, api_type: APIType, proxy_id: Optional[str] = None) -> None:
        """
        Signal that a 429 rate limit error was encountered.
        
        Args:
            api_type: Which API returned 429
            proxy_id: Optional proxy that was used
        """
        current_time = time.time()
        
        # Increment 429 count for this API
        count_key = f"api:{api_type.value}:429_count"
        timestamp_key = f"api:{api_type.value}:last_429"
        
        current_count = self._get(count_key, 0)
        self._put(count_key, current_count + 1)
        self._put(timestamp_key, current_time)
        
        logger.warning(f"429 signaled for {api_type.value} (count: {current_count + 1})")
        
        # Track proxy health if provided
        if proxy_id:
            proxy_key = f"proxy:{proxy_id}:429_count"
            proxy_count = self._get(proxy_key, 0)
            self._put(proxy_key, proxy_count + 1)
            
            # Mark proxy as degraded if threshold exceeded
            if proxy_count + 1 >= PRESSURE_CONFIG["proxy_degraded_threshold"]:
                self._put(f"proxy:{proxy_id}:health", "degraded")
                logger.warning(f"Proxy {proxy_id} marked as degraded")
        
        # Recalculate global pressure
        self._recalculate_pressure()
    
    def _recalculate_pressure(self) -> None:
        """Recalculate and store global pressure score."""
        current_time = time.time()
        window = PRESSURE_CONFIG["recovery_window_seconds"]
        critical = PRESSURE_CONFIG["429_count_critical"]
        
        pressures = []
        for api_type in APIType:
            count_key = f"api:{api_type.value}:429_count"
            timestamp_key = f"api:{api_type.value}:last_429"
            
            count = self._get(count_key, 0)
            last_429 = self._get(timestamp_key, 0)
            
            # Decay count based on time since last 429
            time_since_429 = current_time - last_429 if last_429 else window
            decay_factor = max(0, 1 - (time_since_429 / window))
            effective_count = count * decay_factor
            
            # Calculate pressure for this API (0.0 - 1.0)
            api_pressure = min(1.0, effective_count / critical)
            pressures.append(api_pressure)
        
        # Global pressure is average of all API pressures
        global_pressure = sum(pressures) / len(pressures) if pressures else 0.0
        self._put("global:pressure", global_pressure)
        
        # Calculate recommended delay
        min_delay = PRESSURE_CONFIG["min_delay_seconds"]
        max_delay = PRESSURE_CONFIG["max_delay_seconds"]
        delay = min_delay + (global_pressure * (max_delay - min_delay))
        self._put("global:recommended_delay", delay)
        
        logger.debug(f"Global pressure: {global_pressure:.2f}, delay: {delay:.2f}s")
    
    def get_global_pressure(self) -> float:
        """
        Get current global pressure score.
        
        Returns:
            Pressure score from 0.0 (no pressure) to 1.0 (critical)
        """
        # Recalculate to account for decay
        self._recalculate_pressure()
        return self._get("global:pressure", 0.0)
    
    def get_recommended_delay(self) -> float:
        """
        Get recommended delay before making API request.
        
        Returns:
            Delay in seconds (0.1s to 5.0s based on pressure)
        """
        # Recalculate to account for decay
        self._recalculate_pressure()
        return self._get("global:recommended_delay", PRESSURE_CONFIG["min_delay_seconds"])
    
    def should_pause_spawning(self) -> bool:
        """
        Check if orchestrator should pause spawning new jobs.
        
        Returns:
            True if pressure > pause_threshold (0.8)
        """
        pressure = self.get_global_pressure()
        return pressure > PRESSURE_CONFIG["pause_threshold"]
    
    def can_resume_spawning(self) -> bool:
        """
        Check if orchestrator can resume spawning after pause.
        
        Returns:
            True if pressure < resume_threshold (0.5)
        """
        pressure = self.get_global_pressure()
        return pressure < PRESSURE_CONFIG["resume_threshold"]
    
    def get_healthy_proxy(self, proxy_list: List[str]) -> Optional[str]:
        """
        Get a proxy that is not degraded.
        
        Args:
            proxy_list: List of available proxies
            
        Returns:
            Healthy proxy string or None if all degraded
        """
        import random
        
        healthy = []
        for proxy in proxy_list:
            health_key = f"proxy:{proxy}:health"
            health = self._get(health_key, "healthy")
            if health == "healthy":
                healthy.append(proxy)
        
        if healthy:
            return random.choice(healthy)
        
        # If all degraded, reset and try again
        logger.warning("All proxies degraded, resetting health status")
        for proxy in proxy_list:
            self._put(f"proxy:{proxy}:health", "healthy")
            self._put(f"proxy:{proxy}:429_count", 0)
        
        return random.choice(proxy_list) if proxy_list else None
    
    def get_best_gemini_key(
        self,
        primary: str,
        fallback: str,
        fallback_2: Optional[str] = None,
        fallback_3: Optional[str] = None,
    ) -> Tuple[str, APIType]:
        """
        Get the Gemini API key with fewer recent 429 errors.

        Supports up to 4 keys for maximum rate limit resilience.

        Args:
            primary: Primary Gemini API key
            fallback: Fallback Gemini API key
            fallback_2: Optional second fallback key (tier 3)
            fallback_3: Optional third fallback key (tier 3)

        Returns:
            Tuple of (api_key, key_type)
        """
        # Build list of available keys with their 429 counts
        keys = [
            (primary, APIType.GEMINI_PRIMARY, self._get(f"api:{APIType.GEMINI_PRIMARY.value}:429_count", 0)),
            (fallback, APIType.GEMINI_FALLBACK, self._get(f"api:{APIType.GEMINI_FALLBACK.value}:429_count", 0)),
        ]

        if fallback_2:
            keys.append((fallback_2, APIType.GEMINI_FALLBACK_2, self._get(f"api:{APIType.GEMINI_FALLBACK_2.value}:429_count", 0)))

        if fallback_3:
            keys.append((fallback_3, APIType.GEMINI_FALLBACK_3, self._get(f"api:{APIType.GEMINI_FALLBACK_3.value}:429_count", 0)))

        # Sort by 429 count (ascending) and return the best one
        keys.sort(key=lambda x: x[2])
        best_key, best_type, count = keys[0]

        logger.debug(f"Selected {best_type.value} (429s: {count}) from {len(keys)} keys")
        return (best_key, best_type)
    
    def get_adaptive_batch_size(self) -> int:
        """
        Get recommended batch size based on current pressure.
        
        Returns:
            Batch size (5 to 25 based on pressure)
        """
        pressure = self.get_global_pressure()
        
        if pressure > 0.8:
            return 5   # Minimal - heavy backpressure
        elif pressure > 0.6:
            return 10  # Cautious - reducing load
        elif pressure > 0.3:
            return 15  # Normal - balanced
        else:
            return 25  # Aggressive - maximize throughput
    
    def get_stats(self) -> dict:
        """
        Get current backpressure statistics for monitoring.
        
        Returns:
            Dict with pressure stats for all APIs
        """
        stats = {
            "global_pressure": self.get_global_pressure(),
            "recommended_delay": self.get_recommended_delay(),
            "batch_size": self.get_adaptive_batch_size(),
            "should_pause": self.should_pause_spawning(),
            "apis": {},
        }
        
        for api_type in APIType:
            count_key = f"api:{api_type.value}:429_count"
            timestamp_key = f"api:{api_type.value}:last_429"
            
            stats["apis"][api_type.value] = {
                "429_count": self._get(count_key, 0),
                "last_429": self._get(timestamp_key, 0),
            }
        
        return stats
    
    def reset(self) -> None:
        """Reset all backpressure state (for testing)."""
        for api_type in APIType:
            self._put(f"api:{api_type.value}:429_count", 0)
            self._put(f"api:{api_type.value}:last_429", 0)
        
        self._put("global:pressure", 0.0)
        self._put("global:recommended_delay", PRESSURE_CONFIG["min_delay_seconds"])
        logger.info("Backpressure state reset")


def print_backpressure_stats(bp: BackpressureManager) -> None:
    """Print formatted backpressure statistics."""
    stats = bp.get_stats()
    
    print("\n=== ADAPTIVE CONCURRENCY STATS ===")
    print(f"Global Pressure: {stats['global_pressure']:.2f}")
    print(f"Recommended Delay: {stats['recommended_delay']:.1f}s")
    print(f"Batch Size: {stats['batch_size']}")
    print(f"Spawning: {'PAUSED' if stats['should_pause' ] else 'ACTIVE'}")
    print("---")
    for api_name, api_stats in stats["apis"].items():
        print(f"  {api_name}: {api_stats['429_count']} 429s")
    print("================================\n")
