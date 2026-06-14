One-line: Surface container with optional header/content/footer — the workhorse panel for dashboards and forms.

```jsx
<Card>
  <CardHeader title="Active Portfolio" subtitle="3 positions tracked"
              actions={<Button size="sm" variant="ghost">Refresh</Button>} />
  <CardContent>…</CardContent>
  <CardFooter><Button>Log Trade</Button></CardFooter>
</Card>

<Card variant="compact" interactive>…</Card>
```

- **variant** `compact` pads the card itself (16px); `default` defers padding to CardContent.
- **interactive** brightens the border and lifts the shadow on hover — use for clickable cards.
- Header takes `title`, `subtitle`, and an `actions` slot.
