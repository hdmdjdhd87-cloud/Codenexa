import { describe, expect, it } from "vitest";
import { getModuleComponent } from "@/modules/registry";

describe("module registry (frontend)", () => {
  it("resolves the demo module component", () => {
    const Component = getModuleComponent("codenexa-demo");
    expect(Component).not.toBeNull();
  });

  it("returns null for unknown module_key (не бросает исключение)", () => {
    const Component = getModuleComponent("some-future-module-not-yet-built");
    expect(Component).toBeNull();
  });
});
