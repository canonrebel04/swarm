"""
Skill registry for managing reusable sets of tools and instructions.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
import yaml
import os
from pathlib import Path


@dataclass
class SkillDefinition:
    """Definition of an agent skill."""
    name: str
    description: str
    version: str = "1.0.0"
    allowed_tools: List[str] = field(default_factory=list)
    blocked_tools: List[str] = field(default_factory=list)
    instructions: str = ""  # Markdown instructions from .md file
    metadata: Dict = field(default_factory=dict)


class SkillRegistry:
    """Registry for managing and loading agent skills."""

    def __init__(self, definitions_dir: str = "src/skills/definitions"):
        self.definitions_dir = Path(definitions_dir)
        self._skills: Dict[str, SkillDefinition] = {}
        self.load_all()

    def load_all(self) -> None:
        """Load all skill definitions from the definitions directory."""
        if not self.definitions_dir.exists():
            return

        for yaml_file in self.definitions_dir.glob("*.yaml"):
            try:
                skill_name = yaml_file.stem
                with open(yaml_file, 'r') as f:
                    data = yaml.safe_load(f) or {}
                
                # Load accompanying markdown instructions if available
                md_file = yaml_file.with_suffix(".md")
                instructions = ""
                if md_file.exists():
                    instructions = md_file.read_text().strip()

                skill = SkillDefinition(
                    name=skill_name,
                    description=data.get('description', f"Skill {skill_name}"),
                    version=data.get('version', '1.0.0'),
                    allowed_tools=data.get('may', data.get('allowed_tools', [])),
                    blocked_tools=data.get('may_not', data.get('blocked_tools', [])),
                    instructions=instructions,
                    metadata=data.get('metadata', {})
                )
                self._skills[skill_name] = skill
                
            except Exception as e:
                print(f"Error loading skill {yaml_file}: {e}")

    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        """Get a skill definition by name."""
        return self._skills.get(name)

    def list_skills(self) -> List[str]:
        """List all registered skill names."""
        return list(self._skills.keys())

    def get_all_skills(self) -> List[SkillDefinition]:
        """Get all registered skill definitions."""
        return list(self._skills.values())


# Global registry instance
skill_registry = SkillRegistry()
