import {readFileSync} from "node:fs";
import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {Badge} from "../components/ui/badge";
import {Button} from "../components/ui/button";

const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

describe("semantic dark theme", () => {
  it("keeps the existing light palette unchanged", () => {
    expect(css).toContain("--obliq-canvas: #f8f7f5");
    expect(css).toContain("--obliq-surface: #ffffff");
    expect(css).toContain("--obliq-ink: #191515");
    expect(css).toContain("--obliq-muted: #625d5a");
  });

  it("defines contrast-safe dark interaction and typography tokens", () => {
    expect(css).toContain("--obliq-canvas: #0b1220");
    expect(css).toContain("--obliq-surface: #111827");
    expect(css).toContain("--obliq-surface-raised: #1e293b");
    expect(css).toContain("--obliq-ink: #f1f5f9");
    expect(css).toContain("--obliq-muted: #94a3b8");
    expect(css).toContain("--obliq-interactive-hover: rgba(255, 255, 255, 0.08)");
    expect(css).toContain("--obliq-interactive-active: rgba(96, 165, 250, 0.18)");
    expect(css).toContain("--obliq-focus-ring: rgba(96, 165, 250, 0.38)");
  });

  it("uses semantic action and soft badge colors in shared primitives", () => {
    const button = renderToStaticMarkup(<Button>Continue</Button>);
    const badge = renderToStaticMarkup(<Badge value="partially_received"/>);
    expect(button).toContain("--obliq-action");
    expect(button).toContain("--obliq-action-ink");
    expect(badge).toContain("--obliq-warning-soft");
    expect(badge).toContain("--obliq-warning-ink");
  });

  it("forces Lucide icons to inherit the surrounding text color", () => {
    expect(css).toMatch(/\.lucide\s*\{[^}]*color:\s*currentColor/i);
    expect(css).toMatch(/\.lucide\s*\{[^}]*stroke:\s*currentColor/i);
  });

  it("disables landing motion when the user prefers reduced motion", () => {
    expect(css).toContain(".landing-reveal");
    expect(css).toMatch(/prefers-reduced-motion:\s*reduce[\s\S]*\.landing-reveal/);
  });
});
