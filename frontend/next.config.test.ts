import {afterEach, describe, expect, it, vi} from "vitest";

describe("Next.js deployment output", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("leaves output unset for Vercel framework-managed builds", async () => {
    vi.stubEnv("NEXT_OUTPUT_STANDALONE", "");
    vi.resetModules();

    const {default: config} = await import("./next.config");

    expect(config.output).toBeUndefined();
  });

  it("enables standalone output for the frontend Docker image", async () => {
    vi.stubEnv("NEXT_OUTPUT_STANDALONE", "true");
    vi.resetModules();

    const {default: config} = await import("./next.config");

    expect(config.output).toBe("standalone");
  });
});
