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

## 2024-05-19 - Async Action Buttons Require Immediate Feedback
**Learning:** Destructive or state-changing actions in dynamic lists (like killing or nudging an agent) without immediate visual feedback can cause users to click multiple times, leading to duplicate API calls and frustration.
**Action:** Always wrap async API calls in action buttons with a `try...finally` block that disables the button and updates its text (e.g., adding "...") to give immediate visual confirmation that the request is in flight.
## 2024-05-24 - Form Label Association
**Learning:** For standalone inputs that take up the full width, using an explicit `<label for="...">` with a red required indicator provides much better visual accessibility and context than an off-screen `aria-label`, especially when replacing complex instructions.
**Action:** Always favor visual `<label>` tags with a `for` attribute over `aria-label` for primary form inputs to ensure both visual users and screen readers understand the required context and status.

## 2024-05-25 - Standardized Async Button Feedback
**Learning:** While appending "..." to text provides some visual feedback for async buttons, it lacks semantic context for screen readers and can look unpolished. Adding an SVG spinner combined with `aria-busy="true"` provides a robust, accessible, and visually appealing loading state across the application.
**Action:** Always use a standard SVG spinner and toggle the `aria-busy="true"` attribute on buttons during async operations, ensuring it is cleanly removed in the `finally` block to restore the original state.

## 2026-04-15 - Live Event Stream Empty States
**Learning:** Live event streams (like system logs) that are initially empty can look broken or unpopulated if left completely blank. Users might wonder if the connection failed or if events are simply not happening yet.
**Action:** Always provide an explicit empty state for live event containers with a helpful message explaining why it's empty (e.g., "Waiting for system events...") and apply appropriate `role="log"` and `aria-live="polite"` attributes to ensure screen readers announce incoming events.
