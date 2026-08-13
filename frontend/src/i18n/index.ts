import ru from "./ru";

export type Locale = "ru-RU";

// Реестр локалей. Добавление "en-US" / "kk-KZ" — просто новый ключ здесь
// плюс папка i18n/en, i18n/kk с тем же набором ключей. Компоненты,
// использующие t(), переписывать не нужно.
const dictionaries: Record<Locale, typeof ru> = {
  "ru-RU": ru,
};

const DEFAULT_LOCALE: Locale = "ru-RU";

let currentLocale: Locale = DEFAULT_LOCALE;

export function setLocale(locale: Locale) {
  if (dictionaries[locale]) currentLocale = locale;
}

export function getLocale(): Locale {
  return currentLocale;
}

type Dict = typeof ru;

/** Достаёт значение по пути вида "common.loading" */
export function t(path: string): string {
  const dict = dictionaries[currentLocale] as unknown as Record<string, unknown>;
  const parts = path.split(".");
  let node: unknown = dict;
  for (const part of parts) {
    if (typeof node !== "object" || node === null) return path;
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === "string" ? node : path;
}

export default t;
