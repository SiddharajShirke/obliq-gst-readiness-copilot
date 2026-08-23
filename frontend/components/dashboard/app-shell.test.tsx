import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it, vi} from "vitest";
import {AppShell} from "./app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({replace: vi.fn()}),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: {name: "CA Reviewer", email: "ca@example.test"},
    loading: false,
    logout: vi.fn(),
  }),
}));

vi.mock("@/components/ui/loading", () => ({Loading: () => <div>Loading</div>}));
vi.mock("@/components/ui/theme-toggle", () => ({ThemeToggle: () => <button>Theme</button>}));

describe("primary application navigation", () => {
  it("restores the dynamic alerts workspace without obsolete destinations", () => {
    const html = renderToStaticMarkup(<AppShell><div>Workspace</div></AppShell>);

    for (const label of ["Overview", "Clients", "GST Work", "Alerts", "Settings"]) {
      expect(html).toContain(`>${label}<`);
    }
    expect(html).not.toContain(">Knowledge Base<");
    expect(html).not.toContain(">WhatsApp<");
    expect(html).toContain("href=\"/dashboard/gst-work\"");
    expect(html).toContain("href=\"/dashboard/alerts\"");
  });
});
