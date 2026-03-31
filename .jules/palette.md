## 2024-03-31 - Keyboard Accessibility in Custom Web UI Components
**Learning:** Custom interactive elements like list-item navigation menus (`<li>`) require explicit `tabindex="0"`, appropriate roles (`role="button"`), and visible `:focus-visible` styling to meet standard keyboard accessibility requirements. Without these, screen readers and keyboard-only users cannot navigate the interface properly.
**Action:** When designing or refactoring custom UI shells, always ensure interactive elements have semantic HTML replacements, or apply `tabindex` and `:focus-visible` manually to mimic native accessibility behaviors.

## 2024-03-01 - Default Focus in Destructive Modals
**Learning:** Textual modals do not automatically focus the safest option by default. If a user quickly hits "Enter", they might accidentally trigger the first button (often the destructive one).
**Action:** Always add an `on_mount` method to `ModalScreen` instances with destructive actions to explicitly `focus()` the safe/cancel button (e.g., `#no-button`).