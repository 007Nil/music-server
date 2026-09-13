import logging
from typing import List, Optional

from music_server.audio.backend.base import AudioBackend
from music_server.audio.backend.gstreamer_backend import GStreamerBackend

logger = logging.getLogger(__name__)

# Define available backends with priority order
AVAILABLE_BACKENDS = [
    ("gstreamer", "GStreamer Backend"),
]

def create_audio_backend(name: str = "gstreamer", fallbacks: List[str] | None = None) -> AudioBackend:
    """
    Create an audio backend with optional fallback support.
    
    Args:
        name: Primary backend name to try
        fallbacks: List of fallback backend names to try if primary fails
        
    Returns:
        AudioBackend instance
        
    Raises:
        ValueError: If no available backend can be created
    """
    # If no fallbacks provided, use the default approach
    if fallbacks is None:
        fallbacks = []
    
    # Try primary backend first
    try:
        backend = _create_backend(name)
        logger.info("Successfully created primary backend: %s", name)
        return backend
    except Exception as e:
        logger.warning("Failed to create primary backend %s: %s", name, str(e))
    
    # Try fallback backends
    for fallback_name in fallbacks:
        try:
            backend = _create_backend(fallback_name)
            logger.info("Successfully created fallback backend: %s", fallback_name)
            return backend
        except Exception as e:
            logger.warning("Failed to create fallback backend %s: %s", fallback_name, str(e))
            continue
    
    # If no backends work, try to fall back to gstreamer at least
    try:
        logger.info("Attempting to create fallback to gstreamer backend")
        return GStreamerBackend()
    except Exception as e:
        logger.error("Failed to create any backend, including fallback gstreamer: %s", str(e))
        raise ValueError(f"All audio backends failed to initialize: {str(e)}")


def _create_backend(name: str) -> AudioBackend:
    """Create a specific backend by name."""
    if name == "gstreamer":
        return GStreamerBackend()
    
    raise ValueError(f"Unknown audio backend: {name}")


def get_available_backends() -> List[str]:
    """Get list of available backend names."""
    return [name for name, _ in AVAILABLE_BACKENDS]


def is_backend_available(name: str) -> bool:
    """Check if a backend is available."""
    return name in get_available_backends()


def get_default_backend() -> str:
    """Get the default backend name."""
    if get_available_backends():
        return get_available_backends()[0]
    return "gstreamer"