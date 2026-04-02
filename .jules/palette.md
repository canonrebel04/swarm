
## 2024-04-02 - Missing Async Feedback and Focus Indicators
**Learning:** The UI lacked loading states for async operations (specifically the "Deploy Swarm" button) which could lead to multiple submissions or user confusion. Furthermore, keyboard accessibility was hindered by missing `:focus-visible` indicators and the lack of proper `aria-label`s on icon/action buttons.
**Action:** Implemented a pattern of disabling buttons and altering text during `fetch` requests, wrapped in a `try...finally` block to ensure recovery. Added a global `*:focus-visible` CSS rule for reliable keyboard navigation, and added dynamic `aria-label` attributes to repetitive agent action buttons.
