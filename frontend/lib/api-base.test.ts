import {describe, expect, it} from "vitest";

import * as api from "./api";

type ResolveApiBaseUrl = (configured?: string) => string;

function resolver(): ResolveApiBaseUrl {
  const candidate = api as typeof api & {resolveApiBaseUrl?: ResolveApiBaseUrl};
  expect(candidate.resolveApiBaseUrl).toBeTypeOf("function");
  return candidate.resolveApiBaseUrl as ResolveApiBaseUrl;
}

describe("API base URL", () => {
  it("adds the required API prefix to a host-only deployment URL", () => {
    expect(resolver()("https://obliq-gst-readiness-copilot.onrender.com"))
      .toBe("https://obliq-gst-readiness-copilot.onrender.com/api/v1");
  });

  it("preserves an already-correct API prefix and removes trailing slashes", () => {
    expect(resolver()("https://api.example.com/api/v1///"))
      .toBe("https://api.example.com/api/v1");
  });
});
