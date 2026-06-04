"use client";

import Link from "next/link";

export default function SettingsPage() {
  return (
    <div className="min-h-screen pt-24 pb-24 px-6">
      <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Settings</h1>
      <p className="mt-3 text-[var(--color-text-muted)]">Settings UI is a work-in-progress. Account-level preferences are available under <Link href="/account" className="text-[var(--color-accent)] underline">Account</Link>.</p>
      <div className="mt-6 p-6 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface)]">
        <p className="text-sm text-[var(--color-text-secondary)]">Tell me which settings (profile, notifications, integrations) you want prioritized and I'll scaffold them here.</p>
      </div>
    </div>
  );
}
