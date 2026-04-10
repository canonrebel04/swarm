## 2024-03-31 - Keyboard Accessibility in Custom Web UI Components
**Learning:** Custom interactive elements like list-item navigation menus (`<li>`) require explicit `tabindex="0"`, appropriate roles (`role="button"`), and visible `:focus-visible` styling to meet standard keyboard accessibility requirements. Without these, screen readers and keyboard-only users cannot navigate the interface properly.
**Action:** When designing or refactoring custom UI shells, always ensure interactive elements have semantic HTML replacements, or apply `tabindex` and `:focus-visible` manually to mimic native accessibility behaviors.

## 2024-03-01 - Default Focus in Destructive Modals
**Learning:** Textual modals do not automatically focus the safest option by default. If a user quickly hits "Enter", they might accidentally trigger the first button (often the destructive one).
**Action:** Always add an `on_mount` method to `ModalScreen` instances with destructive actions to explicitly `focus()` the safe/cancel button (e.g., `#no-button`).
## 2024-05-18 - Semantic HTML Over Custom Event Listeners
**Learning:** Native keyboard accessibility (like hitting "Enter" to submit an objective) is much more reliably handled by wrapping inputs in a semantic `<form>` with an `onsubmit` handler, rather than manually attaching `onkeypress` event listeners to individual `<div>` or `<input>` tags.
**Action:** Always refactor isolated input/button pairs into `<form>` tags when handling data submission, and use a `role="alert"` element for displaying inline form errors for screen reader compatibility.
## 2023-10-27 - Accessible Async Success Feedback in SPAs
**Learning:** Repurposing existing `role="alert"` containers for success messages provides immediate screen reader feedback without adding new invisible DOM elements. However, it's crucial to manage the color/styling dynamically and ensure the message clears out to prevent confusing state overlaps.
**Action:** Always consider if an existing ARIA live region can be reused for both error and success states before adding new ones, and ensure clear visual and semantic distinction between state updates.
