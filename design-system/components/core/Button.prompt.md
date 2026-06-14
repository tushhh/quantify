One-line: The primary action control — accent-filled `primary` for the main action, with `secondary`, `ghost`, `danger`, and `link` variants in four sizes.

```jsx
<Button variant="primary" size="md" onClick={run}>Run Backtest</Button>
<Button variant="secondary" icon={<PlusIcon/>}>Log Trade</Button>
<Button variant="ghost" size="sm">Cancel</Button>
<Button variant="danger" loading>Closing…</Button>
```

- **variant**: `primary` (accent), `secondary` (raised surface + border), `ghost` (transparent), `danger` (red fill), `link` (inline accent text).
- **size**: `xs` `sm` `md` `lg` — heights 28/32/36/44px.
- **loading** swaps in a spinner and disables; **icon** renders a leading node (pass a Lucide element).
