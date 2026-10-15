"""CLI interface for Scene Director.

Usage:
    python -m app.services.director.cli --input path/to/roteiro.md --channel fisica --output storage/projects/my_project
"""

import argparse
import json
from pathlib import Path
import sys

from app.services.director.scene_director import SceneDirector


def main():
    parser = argparse.ArgumentParser(description="Fábrica de Shorts — Scene Director CLI")
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the input script file (.md or .txt)",
    )
    parser.add_argument(
        "--script-id", "-id",
        default=None,
        help="Identifier for the script (defaults to input filename stem)",
    )
    parser.add_argument(
        "--channel", "-c",
        default="default",
        help="Channel profile (e.g. fisica, esportes, historia)",
    )
    parser.add_argument(
        "--style", "-s",
        default="editorial",
        help="Visual style preset (e.g. editorial, documentary, energetic)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Target directory to save scenes.json (defaults to storage/projects/<script_id>)",
    )
    parser.add_argument(
        "--provider", "-p",
        choices=["gemini", "local"],
        default="gemini",
        help="Director LLM provider (default: gemini)",
    )

    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.exists():
        print(f"Error: input file {input_file} not found.", file=sys.stderr)
        sys.exit(1)

    script_text = input_file.read_text(encoding="utf-8")
    script_id = args.script_id or input_file.stem

    from app.services.director.scene_director import (
        GeminiDirectorProvider,
        LocalRuleDirectorProvider,
    )

    if args.provider == "local":
        provider = LocalRuleDirectorProvider()
    else:
        provider = GeminiDirectorProvider()

    director = SceneDirector(provider=provider)
    print(f"Directing script '{script_id}' for channel '{args.channel}' using {args.provider}...")

    plan = director.direct_script(
        script_id=script_id,
        script_text=script_text,
        channel=args.channel,
        brand_preset=args.style,
        output_dir=args.output,
    )

    target_dir = Path(args.output) if args.output else Path(f"storage/projects/{script_id}")
    plan_path = target_dir / "scenes.json"

    print(f"\nSuccess! Plan created with {plan.total_scenes} scenes.")
    print(f"Estimated duration: {plan.estimated_duration}s")
    print(f"Saved manifest to: {plan_path}")

    # Print summary of generated scenes
    print("\n--- Scenes Summary ---")
    for sc in plan.scenes:
        print(f"[{sc.scene_id}] ({sc.visual_type}) \"{sc.narration}\"")
        print(f"   Intent: {sc.intent}")
        print(f"   Queries: {', '.join(sc.queries)}")


if __name__ == "__main__":
    main()
