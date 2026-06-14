One-line: Text input with label, hint/error states, accent focus ring, and an optional mono prefix for prices.

```jsx
<Input label="Symbol" placeholder="AAPL" />
<Input label="Buy price" prefix="$" type="number" placeholder="150.00" />
<Input label="Capital" error="Must be at least $1,000" />
```

- **label / hint / error** stack vertically; `error` overrides `hint` and reddens the border.
- **prefix** renders a non-interactive leading glyph in Geist Mono.
- Focus shows a 3px accent ring (`accent-subtle`).
