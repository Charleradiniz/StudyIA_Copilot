import { describe, expect, it } from "vitest";

import { buildAssistantStreamPlan } from "./assistant-stream";

describe("buildAssistantStreamPlan", () => {
  it("keeps the fake streaming duration bounded for long answers", () => {
    const plan = buildAssistantStreamPlan("A".repeat(1800));

    expect(plan.immediate).toBe(false);
    expect(plan.intervalMs).toBe(16);
    expect(plan.charsPerUpdate).toBeGreaterThanOrEqual(100);
  });

  it("renders immediately when reduced motion is preferred", () => {
    const plan = buildAssistantStreamPlan("A moderately long answer", {
      prefersReducedMotion: true,
    });

    expect(plan.immediate).toBe(true);
    expect(plan.charsPerUpdate).toBeGreaterThan(0);
  });

  it("renders extremely long answers immediately to avoid UI drag", () => {
    const plan = buildAssistantStreamPlan("A".repeat(5000));

    expect(plan.immediate).toBe(true);
    expect(plan.charsPerUpdate).toBe(5000);
  });
});
