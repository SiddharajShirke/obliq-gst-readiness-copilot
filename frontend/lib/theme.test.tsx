import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {ThemeProvider, resolveAppliedTheme} from "./theme";
import {ThemeToggle} from "../components/ui/theme-toggle";

describe("application theme", () => {
  it("resolves light, dark, and system preferences deterministically", () => {
    expect(resolveAppliedTheme("light", true)).toBe("light");
    expect(resolveAppliedTheme("dark", false)).toBe("dark");
    expect(resolveAppliedTheme("system", true)).toBe("dark");
    expect(resolveAppliedTheme("system", false)).toBe("light");
  });

  it("renders an accessible labeled top theme control server-safely", () => {
    const html = renderToStaticMarkup(<ThemeProvider><ThemeToggle/></ThemeProvider>);
    expect(html).toContain("Theme:");
    expect(html).toContain("aria-label=\"Change color theme");
    expect(html).toContain("System");
  });
});
