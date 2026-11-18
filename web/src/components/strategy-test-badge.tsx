import { Badge } from "@/components/ui/badge";
import type { StrategyTestResult } from "@/lib/api";

const VARIANT = {
  lost_money: "danger",
  did_not_beat_spy: "warning",
  not_trustworthy: "warning",
  not_testable: "default",
} as const;

/** Short tag saying how the strategy did when tested; the summary is the tooltip. */
export function StrategyTestBadge({ result }: { result?: StrategyTestResult | null }) {
  if (!result) return null;
  return (
    <Badge variant={VARIANT[result.verdict] ?? "default"} title={result.summary} className="shrink-0 whitespace-nowrap">
      {result.label}
    </Badge>
  );
}

/** The test result in full, for expanded panels. */
export function StrategyTestNote({ result }: { result?: StrategyTestResult | null }) {
  if (!result) return null;
  return (
    <p className="text-xs leading-relaxed text-[var(--color-text-secondary)]">
      <span className="font-medium text-[var(--color-text-primary)]">Tested: </span>
      {result.summary}
    </p>
  );
}
