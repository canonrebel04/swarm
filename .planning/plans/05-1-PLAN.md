# Plan 05-1: Enhanced Role Contract Viewer

## Objective
Upgrade the `InspectModal` to provide a comprehensive view of agent roles, displaying both the YAML contract (rules) and the Markdown definition (identity/mission).

## Tasks
1. **Refactor InspectModal**: Use `TabbedContent` from Textual to separate YAML and Markdown views.
2. **Data Loading**:
    - Load `.yaml` from `src/roles/contracts/`.
    - Load `.md` from `src/agents/definitions/`.
3. **YAML Formatting**: Use `RichLog` or `Static` with syntax highlighting (if possible) to display the YAML contract.
4. **Markdown Formatting**: Improve the Markdown display with better styling.
5. **Dismiss Logic**: Ensure the modal is easy to close (Escape or close button).

## Verification
- [ ] Pressing `Ctrl+I` on a selected agent opens the enhanced modal.
- [ ] Both "Contract (Rules)" and "Definition (GSD)" tabs are visible and functional.
- [ ] Correct data is loaded for each role.
