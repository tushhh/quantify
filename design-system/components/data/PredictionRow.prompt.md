One-line: A ranked ML signal row for the "Today's Picks" / screener list — rank, ticker, side, predicted return, drivers and strength.

```jsx
<PredictionRow
  rank={1} symbol="NVDA" side="long"
  predictedReturnPct={2.41} strength={0.182}
  drivers={[
    { feature: "mom_12_1", zscore: 2.07, direction: "higher" },
    { feature: "rsi_14", zscore: -1.4, direction: "lower" },
  ]}
  onClick={() => prefill("NVDA")}
/>
```

- Stack rows inside a `Card` to form the picks table; each row has a bottom hairline.
- **side** drives the LONG/SHORT badge color; return + strength are colored by sign and rendered in mono/tabular.
- Composes `Badge` and `DriverPill` — don't re-implement those.
