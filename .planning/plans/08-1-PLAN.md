# Plan 08-1: Skill Data Model & Registry

## Objective
Implement the core `Skill` data model and registration system.

## Tasks
1. **Directory Structure**: Create `src/skills/definitions/`.
2. **Data Model**: Define `SkillDefinition` dataclass in `src/skills/registry.py`.
3. **Registry Logic**: Implement `SkillRegistry` to load YAML/MD files from the definitions directory.
4. **Initial Skills**: Create a few baseline skills (e.g., `web_research`, `sql_expert`).

## Verification
- [ ] `SkillRegistry.list_skills()` returns loaded skills.
- [ ] Correct parsing of YAML/MD skill pairs.
