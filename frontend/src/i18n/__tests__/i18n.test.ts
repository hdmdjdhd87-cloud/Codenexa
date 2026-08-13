import { describe, expect, it } from "vitest";
import t, { getLocale } from "@/i18n";

describe("i18n", () => {
  it("defaults to ru-RU", () => {
    expect(getLocale()).toBe("ru-RU");
  });

  it("resolves a nested key to Russian text", () => {
    expect(t("common.loading")).toBe("Загрузка…");
  });

  it("falls back to the key itself for unknown paths (не падает)", () => {
    expect(t("nonexistent.key")).toBe("nonexistent.key");
  });

  it("has no English UI strings among common keys (п.3 спецификации)", () => {
    const values = ["common.loading", "nav.home", "nav.catalog", "empty.modules"].map(t);
    for (const v of values) {
      expect(v).not.toMatch(/^(Home|Apps|Settings|Loading|Profile)$/);
    }
  });
});
