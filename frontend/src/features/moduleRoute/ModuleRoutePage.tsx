import { Suspense, useEffect } from "react";
import { useParams } from "react-router-dom";
import t from "@/i18n";
import { useModules } from "@/hooks/useModules";
import { moduleService } from "@/services/moduleService";
import { getModuleComponent } from "@/modules/registry";
import { LoadingState } from "@/components/states/LoadingState";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";

export function ModuleRoutePage() {
  const { moduleKey } = useParams<{ moduleKey: string }>();
  const modules = useModules();

  const module = modules.data?.find((m) => m.module_key === moduleKey);
  const Component = moduleKey ? getModuleComponent(moduleKey) : null;

  useEffect(() => {
    document.title = module ? `${module.name} — CodeNexa` : "CodeNexa";
  }, [module]);

  useEffect(() => {
    // Регистрируем факт открытия модуля в истории (backend-событие,
    // см. app/routers/modules.py::get_module). Fire-and-forget — не
    // должно блокировать сам просмотр модуля при сетевой заминке.
    if (module?.id) {
      moduleService.get(module.id).catch(() => {
        /* не критично для UX — просто не залогируется в историю */
      });
    }
  }, [module?.id]);


  if (modules.isLoading) return <LoadingState />;
  if (modules.isError) return <ErrorState message={t("errors.loadModules")} onRetry={() => modules.refetch()} />;

  if (!module) {
    return <EmptyState title={t("empty.modules")} />;
  }

  if (module.status === "maintenance" || !Component) {
    // COMING_SOON / модуль ещё без frontend-компонента — нормальное
    // информационное состояние, а не переход на несуществующую страницу (п.20).
    return (
      <div className="px-4 pt-8">
        <EmptyState title={module.name} description={t("catalog.comingSoonDetail")} />
      </div>
    );
  }

  return (
    <Suspense fallback={<LoadingState />}>
      <Component />
    </Suspense>
  );
}
