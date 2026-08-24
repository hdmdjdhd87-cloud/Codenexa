export const CATEGORY_LABELS: Record<string, string> = {
  business: "Деловые",
  personal: "Личные",
  legal: "Юридические",
  universal: "Универсальные",
};

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}
