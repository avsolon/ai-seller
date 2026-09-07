"""Tool Registry (doc 11): maps tool names to executable tools."""

from __future__ import annotations

from typing import Dict, List, Optional

from app.ai.tools.base import Tool


class ToolRegistry:
    """Registers and resolves business tools by name."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def register_many(self, tools: List[Tool]) -> None:
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return sorted(self._tools)
