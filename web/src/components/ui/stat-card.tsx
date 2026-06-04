import { clsx } from "clsx";
import { LucideIcon, TrendingDown, TrendingUp } from "lucide-react";
import { Card, CardContent } from "./card";

interface StatCardProps {
  title: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  icon?: LucideIcon;
  className?: string;
}

export function StatCard({ title, value, change, changeLabel, icon: Icon, className }: StatCardProps) {
  const isPositive = change !== undefined && change >= 0;
  return (
    <Card className={clsx("hover:shadow-[var(--shadow-md)] transition-shadow duration-200", className)}>
      <CardContent className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <p className="text-sm text-[var(--color-text-muted)] font-medium">{title}</p>
          <p className="text-2xl font-bold tracking-tight text-[var(--color-text-primary)]">{value}</p>
          {change !== undefined && (
            <div className={clsx("flex items-center gap-1 text-xs font-medium", isPositive ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
              {isPositive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              {isPositive ? "+" : ""}{change}% {changeLabel ?? "vs last period"}
            </div>
          )}
        </div>
        {Icon && (
          <div className="p-2.5 rounded-[var(--radius-md)] bg-[var(--color-accent-subtle)]">
            <Icon className="h-5 w-5 text-[var(--color-accent)]" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
