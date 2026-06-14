One-line: Inline status banner for confirmations, validation errors and risk alerts.

```jsx
<Alert variant="success" title="Trade logged">Telegram alert activated if connected.</Alert>
<Alert variant="danger">Symbol could not be verified.</Alert>
<Alert variant="warning" title="Drawdown">NVDA is −10.4% vs entry.</Alert>
```

- **variant**: `info` `success` `danger` `warning` — tinted background, matching border + glyph badge.
- **title** is optional; pass body text as children. Override the glyph with **icon**.
