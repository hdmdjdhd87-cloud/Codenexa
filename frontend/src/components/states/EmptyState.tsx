interface EmptyStateProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center px-6">
      <div className="w-12 h-12 rounded-2xl bg-surface-elevated border border-border mb-4" aria-hidden="true" />
      <p className="text-text-primary font-medium text-[15px]">{title}</p>
      {description && <p className="text-text-secondary text-[13px] mt-1.5 max-w-[260px]">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
