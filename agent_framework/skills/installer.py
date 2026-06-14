"""Skill installer module - download and install skills from URLs/GitHub.

Supports:
- GitHub repo URLs (download SKILL.md from raw)
- Direct URL downloads
- Local file paths
- Validation and registration
"""

from __future__ import annotations
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..web.search import WebClient
from ..core.types import SkillSpec

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────

SKILL_STORE_DIR = Path(__file__).parent / "store"
MAX_SKILL_SIZE = 1024 * 1024  # 1MB max skill file
ALLOWED_SKILL_EXTENSIONS = [".md", ".yaml", ".yml", ".json"]

# GitHub raw content base URLs
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"
GITHUB_API_BASE = "https://api.github.com"


class SkillInstaller:
    """Install skills from various sources into the local skill store."""

    def __init__(self, store_dir: Optional[str] = None):
        self._store_dir = Path(store_dir) if store_dir else SKILL_STORE_DIR
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._web = WebClient()

    async def install_from_github(
        self,
        repo_url: str,
        branch: str = "main",
        skill_path: str = "SKILL.md",
    ) -> SkillSpec:
        """Install a skill from a GitHub repository.

        Args:
            repo_url: GitHub repo URL (https://github.com/user/repo)
            branch: Branch name (default: main)
            skill_path: Path to SKILL.md in the repo (default: SKILL.md)

        Returns:
            SkillSpec with parsed skill metadata
        """
        # Parse repo URL
        repo_path = self._parse_github_url(repo_url)
        if not repo_path:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")

        raw_url = f"{GITHUB_RAW_BASE}/{repo_path}/{branch}/{skill_path}"
        return await self.install_from_url(raw_url)

    async def install_from_url(self, url: str) -> SkillSpec:
        """Install a skill from a URL.

        Supports:
        - Raw GitHub URLs (raw.githubusercontent.com)
        - Any downloadable URL pointing to a skill file

        Args:
            url: Direct URL to a skill file (.md, .yaml, .yml, .json)

        Returns:
            SkillSpec with parsed skill metadata
        """
        # Download content
        result = await self._web.request(url)

        if not result.get("success"):
            err_code = result.get("status_code", "unknown")
            err_msg = result.get("error", "HTTP " + str(err_code))
            raise RuntimeError(
                "Failed to download skill from %s: %s" % (url, err_msg)
            )

        content = result.get("content", "")
        if not content:
            raise RuntimeError(f"Empty response from {url}")

        # Check size
        if len(content) > MAX_SKILL_SIZE:
            raise RuntimeError(f"Skill file too large ({len(content)} bytes)")

        # Validate and parse
        skill = self._parse_skill_content(content, url)

        # Save to store
        self._save_skill(skill)

        logger.info(f"Installed skill '{skill.name}' from {url}")
        return skill

    async def install_from_path(self, path: str) -> SkillSpec:
        """Install a skill from a local file path.

        Args:
            path: Local path to a skill file

        Returns:
            SkillSpec with parsed skill metadata
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Skill file not found: {path}")

        if path_obj.suffix.lower() not in ALLOWED_SKILL_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension '{path_obj.suffix}'. "
                f"Allowed: {ALLOWED_SKILL_EXTENSIONS}"
            )

        with open(path_obj, "r", encoding="utf-8") as f:
            content = f.read()

        skill = self._parse_skill_content(content, str(path_obj))
        self._save_skill(skill)

        logger.info(f"Installed skill '{skill.name}' from {path}")
        return skill

    # ── Internal methods ──────────────────────────────────────

    def _parse_github_url(self, url: str) -> Optional[str]:
        """Parse GitHub URL to get repo path (user/repo)."""
        patterns = [
            r"github\.com/([^/]+/[^/]+?)(?:\.git)?$",
            r"github\.com/([^/]+/[^/]+?)/(?:tree|blob)/",
            r"github\.com/([^/]+/[^/]+?)/",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1).rstrip("/")
        return None

    def _parse_skill_content(self, content: str, source: str) -> SkillSpec:
        """Parse skill content into a SkillSpec.

        Supports:
        - Markdown (SKILL.md format with # Title, ## Description, ## Instructions)
        - YAML/JSON format (simple key: value)
        """
        lines = content.strip().split("\n")
        name = "unnamed_skill"
        description = ""
        instructions = content
        required_tools: List[str] = []
        metadata: Dict[str, Any] = {"source": source}

        # Try JSON first
        if content.strip().startswith("{"):
            try:
                data = json.loads(content)
                name = data.get("name", name)
                description = data.get("description", description)
                instructions = data.get("instructions", instructions)
                required_tools = data.get("requires", required_tools)
                metadata.update(data.get("metadata", {}))
                return SkillSpec(
                    name=name,
                    description=description,
                    instructions=instructions,
                    required_tools=required_tools,
                    metadata=metadata,
                )
            except json.JSONDecodeError:
                pass

        # Parse Markdown format
        in_code_block = False
        for i, line in enumerate(lines):
            # Track code blocks
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            stripped = line.strip()

            # Title (# Name)
            if stripped.startswith("# ") and i < 5:
                name = stripped[2:].strip()

            # Description (## Description)
            elif stripped.startswith("## Description") and i + 1 < len(lines):
                desc_lines = []
                for dl in lines[i + 1:]:
                    if dl.strip().startswith("## ") or dl.strip().startswith("```"):
                        break
                    if dl.strip():
                        desc_lines.append(dl.strip())
                description = " ".join(desc_lines)

            # Requires (## Requires)
            elif stripped.startswith("## Requires") and i + 1 < len(lines):
                req_line = lines[i + 1].strip()
                required_tools = [t.strip() for t in req_line.split(",") if t.strip()]

            # Category
            elif stripped.startswith("## Category") and i + 1 < len(lines):
                metadata["category"] = lines[i + 1].strip()

            # Name from key: value format
            elif stripped.startswith("name:") and i < 10:
                name = stripped[5:].strip()

            elif stripped.startswith("description:") and i < 10:
                description = stripped[12:].strip()

        return SkillSpec(
            name=name,
            description=description,
            instructions=instructions,
            required_tools=required_tools,
            metadata=metadata,
        )

    def _save_skill(self, skill: SkillSpec) -> None:
        """Save skill to local store as JSON."""
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", skill.name)
        skill_file = self._store_dir / f"{safe_name}.json"

        data = {
            "name": skill.name,
            "description": skill.description,
            "instructions": skill.instructions,
            "required_tools": skill.required_tools,
            "metadata": skill.metadata,
        }
        with open(skill_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def list_installed(self) -> List[SkillSpec]:
        """List all installed skills in the store."""
        skills = []
        if not self._store_dir.exists():
            return skills
        for f in sorted(self._store_dir.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                skills.append(SkillSpec(
                    name=data.get("name", f.stem),
                    description=data.get("description", ""),
                    instructions=data.get("instructions", ""),
                    required_tools=data.get("required_tools", []),
                    metadata=data.get("metadata", {}),
                ))
            except Exception as e:
                logger.warning(f"Failed to load skill from {f}: {e}")
        return skills

    def remove_skill(self, name: str) -> bool:
        """Remove a skill from the store by name."""
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        skill_file = self._store_dir / f"{safe_name}.json"
        if skill_file.exists():
            skill_file.unlink()
            logger.info(f"Removed skill '{name}'")
            return True
        return False


# ── Convenience function ──────────────────────────────────────

_default_installer = SkillInstaller()


async def install_skill(source: str) -> SkillSpec:
    """Install a skill from a URL or local path.

    Args:
        source: GitHub URL, direct URL, or local file path

    Returns:
        SkillSpec with parsed skill metadata
    """
    if source.startswith(("http://", "https://")):
        if "github.com" in source and "/blob/" in source:
            # Convert GitHub blob URL to raw URL
            source = source.replace("github.com", "raw.githubusercontent.com")
            source = source.replace("/blob/", "/")
        return await _default_installer.install_from_url(source)
    else:
        return await _default_installer.install_from_path(source)


async def search_and_install_skills(query: str) -> List[SkillSpec]:
    """Search the web for a skill and install it.

    Args:
        query: Search query for finding skills

    Returns:
        List of installed SkillSpecs
    """
    from .search import web_search as ws

    results = await ws(query, num_results=5)
    installed = []

    for result in results:
        url = result.get("url", "")
        if not url:
            continue

        # Try to find SKILL.md or similar files
        if "github.com" in url:
            try:
                # Find raw SKILL.md URL
                if "/blob/" in url:
                    raw_url = url.replace("github.com", "raw.githubusercontent.com")
                    raw_url = raw_url.replace("/blob/", "/")
                elif url.endswith(".md"):
                    raw_url = url
                else:
                    # Assume repo root, try SKILL.md
                    repo_match = re.search(r"github\.com/([^/]+/[^/]+)", url)
                    if repo_match:
                        raw_url = f"https://raw.githubusercontent.com/{repo_match.group(1)}/main/SKILL.md"
                    else:
                        continue

                skill = await _default_installer.install_from_url(raw_url)
                installed.append(skill)
                logger.info(f"Installed skill from {raw_url}")
            except Exception as e:
                logger.warning(f"Failed to install from {url}: {e}")
                continue

        elif url.endswith((".md", ".yaml", ".yml", ".json")):
            try:
                skill = await _default_installer.install_from_url(url)
                installed.append(skill)
            except Exception as e:
                logger.warning(f"Failed to install from {url}: {e}")

    return installed
