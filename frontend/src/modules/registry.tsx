import { lazy } from "react";

/**
 * Единственная точка, где Core "знает" о существовании конкретных
 * модулей — просто список lazy-компонентов по module_key. Никаких
 * if (module === "...") в Home/Catalog/Profile и т.д. (п.13).
 *
 * Добавление нового модуля:
 *  1. INSERT в nexa_modules (миграция) — модуль появляется в каталоге.
 *  2. Добавить одну строку сюда, указывающую на его lazy-компонент.
 * Всё. Остальной Core трогать не нужно. Подробнее — docs/modules.md.
 */
export const MODULE_COMPONENTS: Record<string, React.LazyExoticComponent<React.ComponentType>> = {
  "codenexa-demo": lazy(() => import("./demo/DemoModulePage").then((m) => ({ default: m.DemoModulePage }))),
  "ai-docs": lazy(() => import("./aidocs/AiDocsApp").then((m) => ({ default: m.AiDocsApp }))),
};

export function getModuleComponent(moduleKey: string) {
  return MODULE_COMPONENTS[moduleKey] ?? null;
}
