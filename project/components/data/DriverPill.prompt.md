One-line: One feature driver behind a prediction — mono feature name, z-score, and a ▲/▼ favorability arrow.

```jsx
<DriverPill feature="mom_12_1" zscore={2.07} direction="higher" />
<DriverPill feature="rsi_14" zscore={-1.84} direction="lower" />
```

- **direction** `higher` → green ▲ (higher is favorable); `lower` → red ▼.
- Group three of these under a prediction to explain the model's call. Used inside PredictionRow.
