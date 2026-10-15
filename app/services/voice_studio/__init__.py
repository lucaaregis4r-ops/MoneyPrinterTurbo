"""Voice Studio package for Fábrica de Shorts.
Provides TTS engine management, phrase previews, and pronunciation dictionaries.
"""

from .voice_provider import EdgeVoiceProvider, FallbackVoiceProvider, VoiceProvider
from .voice_service import VoiceStudioService

__all__ = [
    "VoiceProvider",
    "EdgeVoiceProvider",
    "FallbackVoiceProvider",
    "VoiceStudioService",
]
