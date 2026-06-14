One-line: KPI tile — label, large tabular value, optional signed delta and an accent icon tile.

```jsx
<StatCard label="Sharpe Ratio" value="1.84" change={6.2} icon={<ActivityIcon/>} />
<StatCard label="Max Drawdown" value="−14.2%" change={-2.1} changeLabel="vs benchmark" />
<StatCard label="Open Positions" value={7} />
```

- **change** sign drives the green/red ▲/▼ delta; omit for a plain stat.
- **value** is rendered with tabular-nums — format it (currency, %, ratio) before passing.
