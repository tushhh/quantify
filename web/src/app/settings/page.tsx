import Link from "next/link";
import { UserCircle } from "lucide-react";

export default function SettingsPage() {
  return (
    <div className="max-w-2xl pt-8 pb-16">
      <h1 className="text-2xl font-semibold text-[var(--color-text-primary)]">Settings</h1>
      <div className="mt-6 p-6 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface)] flex items-start gap-4">
        <UserCircle className="h-6 w-6 shrink-0 text-[var(--color-text-secondary)]" />
        <div>
          <p className="text-sm font-medium text-[var(--color-text-primary)]">Your preferences live on your account page</p>
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
            Link your Telegram username for alerts and change your password there. Switch between light and dark mode with the theme button in the top bar.
          </p>
          <Link
            href="/account"
            className="mt-4 inline-flex items-center rounded-[var(--radius-md)] bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-[var(--color-accent-foreground)] hover:bg-[var(--color-accent-hover)] transition-colors"
          >
            Open account
          </Link>
        </div>
      </div>
    </div>
  );
}
