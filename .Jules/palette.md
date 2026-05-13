## 2024-05-13 - Slider Accessibility
**Learning:** Reusable input components (like Slider) often lack proper label-to-input association out of the box, breaking screen reader functionality and reducing click targets.
**Action:** Always use React's `useId()` hook to generate unique IDs for linking labels via `htmlFor` to inputs inside generic components to ensure accessibility across all instances.

## 2025-02-18 - Improve Strategy Configurator Collapse Toggle Accessibility
**Learning:** Found an icon-only button lacking accessible name and keyboard focus states in the Strategy Configurator. Adding dynamic `aria-label`, `aria-expanded`, and visible focus rings significantly improves interaction for screen-reader and keyboard users without altering visual design.
**Action:** Always verify icon-only buttons have descriptive ARIA labels, semantic state attributes like `aria-expanded` (if they toggle content), and clear `focus-visible` styling using Tailwind. Avoid using `npm` commands; stick to `pnpm` as per project constraints to prevent lockfile churn.
