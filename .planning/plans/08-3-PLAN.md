# Plan 08-3: TUI Skill Browser

## Objective
Add a dedicated viewer in the TUI to browse available skills.

## Tasks
1. **New Modal**: Create `src/tui/screens/skills.py` with `SkillBrowserModal`.
2. **Tabbed View**: Show "Description" and "Tools/Instructions" for each skill.
3. **Keybinding**: Add `ctrl+s` to `SwarmApp` to open the skill browser.
4. **Theme Integration**: Use consistent styling with the `InspectModal`.

## Verification
- [ ] `Ctrl+S` opens the skill browser.
- [ ] All registered skills are listed and detailed view works.
