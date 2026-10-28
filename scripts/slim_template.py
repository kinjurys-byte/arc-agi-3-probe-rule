"""Replace the agent template's agents/__init__.py with a minimal one.

The official ARC-AGI-3 agent template (MIT, cloned into vendor/ as the README
describes) imports every LLM-backed example agent in agents/__init__.py
(LangGraph, LangSmith, smolagents, OpenAI). This repository installs none of
those packages, and the runner only needs the template's base classes, so the
import fails. This script writes a minimal __init__.py that registers the
template's random agent only, as the official Kaggle sample notebooks do at
run time. Run it once after cloning the template.

usage: python scripts/slim_template.py [path/to/ARC-AGI-3-Agents]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MINIMAL_INIT = '''"""Minimal agents package (scripts/slim_template.py): random agent only."""
from typing import Type

from dotenv import load_dotenv

from .agent import Agent, Playback
from .swarm import Swarm
from .templates.random_agent import Random

load_dotenv()

AVAILABLE_AGENTS: dict[str, Type[Agent]] = {
    "random": Random,
}
'''


def main() -> None:
    template = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "vendor" / "ARC-AGI-3-Agents"
    init = template / "agents" / "__init__.py"
    if not init.exists():
        raise SystemExit(f"agent template not found at {template}; clone it first (README, Setup)")
    init.write_text(MINIMAL_INIT)
    print(f"wrote {init}")


if __name__ == "__main__":
    main()
