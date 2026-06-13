"""技能系统测试。"""

import os
import tempfile
import pytest
from agent_framework.skills.manager import DefaultSkillManager


@pytest.mark.asyncio
async def test_list_empty():
    mgr = DefaultSkillManager()
    assert mgr.list_skills() == []


@pytest.mark.asyncio
async def test_unload_nonexistent():
    mgr = DefaultSkillManager()
    result = await mgr.unload_skill("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_load_unload():
    mgr = DefaultSkillManager()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write("# MySkill\n\n## Description\n\n测试技能\n\n执行以下步骤...")
        tmp_path = f.name

    try:
        spec = await mgr.load_skill(tmp_path)
        assert spec.name is not None
        assert len(mgr.list_skills()) == 1

        result = await mgr.unload_skill(spec.name)
        assert result is True
        assert mgr.list_skills() == []
    finally:
        os.unlink(tmp_path)
