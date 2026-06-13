from __future__ import annotations
import dataclasses
from typing import Any, Dict, List, Optional
from .core.types import ContextLimit, SandboxMode


@dataclasses.dataclass
class AgentConfig:
    """Agent 全局配置"""
    model: str = "gpt-4o"
    max_iterations: int = 50
    context_limit: ContextLimit = dataclasses.field(default_factory=ContextLimit)
    sandbox_mode: SandboxMode = SandboxMode.RESTRICTED
    working_directory: str = "."
    memory_path: Optional[str] = None
    skill_dirs: List[str] = dataclasses.field(default_factory=list)
    extra: Dict[str, Any] = dataclasses.field(default_factory=dict)

    @classmethod
    def default(cls) -> "AgentConfig":
        return cls()
