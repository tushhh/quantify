"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { TradeLogTable } from "@/components/TradeLogTable";
import { Card } from "@/components/ui";

export default function TradesPage() {
  const router = useRouter();
  // Redirect to dashboard since trades page is consolidated there
  useEffect(() => {
    router.push("/dashboard");
  }, [router]);

  const [trades, setTrades] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    api.trades.list()
      .then((res) => {
        if (!mounted) return;
        setTrades(res ?? []);
      })
      .catch((err) => {
        console.error(err);
        if (!mounted) return;
        setError(err?.message ?? "Failed to load trades");
      })
      .finally(() => {
        if (!mounted) return;
        setLoading(false);
      });
    return () => { mounted = false; };
  }, []);

  return (
    <div className="min-h-screen pt-16 pb-16 px-6">
      <div className="max-w-[1400px] mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Trades</h1>
        </div>

        <Card>
          {loading ? (
            <div className="p-6 text-[var(--color-text-muted)]">Loading trades…</div>
          ) : error ? (
            <div className="p-6 text-[var(--color-danger)]">{error}</div>
          ) : (
            <TradeLogTable trades={trades} />
          )}
        </Card>
      </div>
    </div>
  );
}
