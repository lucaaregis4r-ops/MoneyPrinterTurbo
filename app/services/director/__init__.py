"""Director package for Fábrica de Shorts.
Transforms locked human scripts into structured scene plans.
"""

from .prompt_builder import SYSTEM_INSTRUCTION, build_director_prompt
from .scene_director import (
    DirectorProvider,
    GeminiDirectorProvider,
    LocalRuleDirectorProvider,
    SceneDirector,
)
from .schemas import MotionType, Scene, ScenePlan, VisualType
from .scene_validator import realign_narration_with_original, validate_scene_plan

__all__ = [
    "SYSTEM_INSTRUCTION",
    "build_director_prompt",
    "DirectorProvider",
    "GeminiDirectorProvider",
    "LocalRuleDirectorProvider",
    "SceneDirector",
    "MotionType",
    "Scene",
    "ScenePlan",
    "VisualType",
    "realign_narration_with_original",
    "validate_scene_plan",
]
