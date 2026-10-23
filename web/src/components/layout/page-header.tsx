// One page heading pattern for the whole app: a plain title and one sentence on what the page is for.
export default function PageHeader({ title, description, children }: {
  title: string;
  description?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-3xl">
        <h1 className="text-[25px] leading-tight font-semibold tracking-tight text-[var(--color-text-primary)]">{title}</h1>
        {description && <p className="mt-1.5 text-sm leading-relaxed text-[var(--color-text-secondary)]">{description}</p>}
      </div>
      {children}
    </header>
  );
}
