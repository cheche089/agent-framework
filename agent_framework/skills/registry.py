"""Skill Registry - persistent storage for installed skills.

Provides CRUD operations for skills stored as JSON files.
Auto-loads on startup and integrates with the SkillManager.
"""

from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.types import SkillSpec

logger = logging.getLogger(__name__)

REGISTRY_FILE = Path(__file__).parent / "registry.json"


class SkillRegistry:
    """Registry for managing installed skills with JSON persistence."""

    def __init__(self, registry_path: Optional[str] = None):
        self._path = Path(registry_path) if registry_path else REGISTRY_FILE
        self._skills: Dict[str, SkillSpec] = {}
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, entry in data.get("skills", {}).items():
                    self._skills[name] = SkillSpec(
                        name=entry.get("name", name),
                        description=entry.get("description", ""),
                        instructions=entry.get("instructions", ""),
                        required_tools=entry.get("required_tools", []),
                        metadata=entry.get("metadata", {}),
                    )
                logger.info(f"Loaded {len(self._skills)} skills from registry")
            except Exception as e:
                logger.warning(f"Failed to load registry: {e}")

    def _save(self) -> None:
        """Save registry to disk."""
        data = {
            "skills": {
                name: {
                    "name": spec.name,
                    "description": spec.description,
                    "instructions": spec.instructions,
                    "required_tools": spec.required_tools,
                    "metadata": spec.metadata,
                }
                for name, spec in self._skills.items()
            }
        }
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save registry: {e}")

    def register(self, skill: SkillSpec) -> None:
        """Register a skill in the registry."""
        self._skills[skill.name] = skill
        self._save()
        logger.info(f"Registered skill '{skill.name}'")

    def unregister(self, name: str) -> bool:
        """Remove a skill from the registry."""
        if name in self._skills:
            del self._skills[name]
            self._save()
            logger.info(f"Unregistered skill '{name}'")
            return True
        return False

    def get(self, name: str) -> Optional[SkillSpec]:
        """Get a skill by name."""
        return self._skills.get(name)

    def list(self) -> List[SkillSpec]:
        """List all registered skills."""
        return list(self._skills.values())

    def has(self, name: str) -> bool:
        """Check if a skill is registered."""
        return name in self._skills

    def search(self, query: str) -> List[SkillSpec]:
        """Search skills by name or description."""
        query = query.lower()
        results = []
        for skill in self._skills.values():
            if query in skill.name.lower() or query in skill.description.lower():
                results.append(skill)
        return results

    def clear(self) -> None:
        """Clear all skills from registry."""
        self._skills.clear()
        self._save()

    @property
    def count(self) -> int:
        return len(self._skills)
