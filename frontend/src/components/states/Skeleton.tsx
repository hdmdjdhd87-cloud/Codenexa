interface SkeletonProps {
  className?: string;
}

/** Простой пульсирующий плейсхолдер — используется вместо спиннера там,
 * где заранее известна форма контента (карточки модулей, профиль). */
export function Skeleton({ className = "" }: SkeletonProps) {
  return <div className={`animate-pulse rounded-xl bg-surface-elevated ${className}`} aria-hidden="true" />;
}

export function ModuleCardSkeleton() {
  return (
    <div className="rounded-2xl bg-surface border border-border p-4 flex items-start gap-3">
      <Skeleton className="w-11 h-11 shrink-0" />
      <div className="min-w-0 flex-1 flex flex-col gap-2">
        <Skeleton className="h-3.5 w-2/3" />
        <Skeleton className="h-3 w-4/5" />
      </div>
    </div>
  );
}

export function ModuleListSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-2.5" role="status" aria-label="Загрузка">
      {Array.from({ length: count }).map((_, i) => (
        <ModuleCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function ProfileHeaderSkeleton() {
  return (
    <div className="flex items-center gap-3.5" role="status" aria-label="Загрузка">
      <Skeleton className="w-16 h-16 rounded-2xl" />
      <div className="flex flex-col gap-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-20" />
      </div>
    </div>
  );
}
