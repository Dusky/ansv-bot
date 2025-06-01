"""
LRU Cache implementation for user and channel color management.
"""

from collections import OrderedDict
from typing import Any, Optional


class LRUCache:
    """Memory-efficient LRU (Least Recently Used) cache to prevent memory leaks."""
    
    def __init__(self, maxsize: int = 1000):
        self.maxsize = maxsize
        self.cache = OrderedDict()
    
    def __contains__(self, key: Any) -> bool:
        return key in self.cache
    
    def __getitem__(self, key: Any) -> Any:
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        raise KeyError(key)
    
    def __setitem__(self, key: Any, value: Any) -> None:
        if key in self.cache:
            # Update existing key and move to end
            self.cache[key] = value
            self.cache.move_to_end(key)
        else:
            # Add new key
            self.cache[key] = value
            # Remove oldest if over size limit
            if len(self.cache) > self.maxsize:
                self.cache.popitem(last=False)  # Remove oldest (first) item
    
    def get(self, key: Any, default: Optional[Any] = None) -> Any:
        """Get value by key, returning default if not found."""
        try:
            return self[key]
        except KeyError:
            return default
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
    
    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)