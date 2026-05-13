## 2024-05-13 - Slider Accessibility
**Learning:** Reusable input components (like Slider) often lack proper label-to-input association out of the box, breaking screen reader functionality and reducing click targets.
**Action:** Always use React's `useId()` hook to generate unique IDs for linking labels via `htmlFor` to inputs inside generic components to ensure accessibility across all instances.
