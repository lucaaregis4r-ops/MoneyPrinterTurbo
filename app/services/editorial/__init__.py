"""Editorial package for Fábrica de Shorts.
Handles human script management, versioning, directive parsing, and pronunciation dictionary.
"""

from .directives import ScriptDirective, parse_directives, strip_directives
from .pronunciation import PronunciationEngine
from .script_manager import ScriptManager, ScriptVersion

__all__ = [
    "ScriptDirective",
    "parse_directives",
    "strip_directives",
    "PronunciationEngine",
    "ScriptManager",
    "ScriptVersion",
]
