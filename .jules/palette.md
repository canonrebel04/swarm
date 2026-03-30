## 2024-03-01 - Default Focus in Destructive Modals
**Learning:** Textual modals do not automatically focus the safest option by default. If a user quickly hits "Enter", they might accidentally trigger the first button (often the destructive one).
**Action:** Always add an `on_mount` method to `ModalScreen` instances with destructive actions to explicitly `focus()` the safe/cancel button (e.g., `#no-button`).
