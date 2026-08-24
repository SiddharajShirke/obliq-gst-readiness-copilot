import {renderToStaticMarkup} from "react-dom/server";
import type {ButtonHTMLAttributes, InputHTMLAttributes, ReactNode} from "react";
import {describe, expect, it, vi} from "vitest";

import RegisterPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({replace: vi.fn()}),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({register: vi.fn()}),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({children, ...props}: ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button {...props}>{children}</button>
  ),
}));

vi.mock("@/components/ui/field", () => ({
  Field: ({label, children}: {label: string; children: ReactNode}) => (
    <label>{label}{children}</label>
  ),
  Input: (props: InputHTMLAttributes<HTMLInputElement>) => <input {...props}/>,
}));

vi.mock("sonner", () => ({
  toast: {success: vi.fn(), error: vi.fn()},
}));

describe("direct account registration", () => {
  it("presents immediate workspace creation without an email-confirmation action", () => {
    const html = renderToStaticMarkup(<RegisterPage/>);

    expect(html).toContain("Create a secure CA workspace");
    expect(html).toContain("add any number of client profiles");
    expect(html).not.toContain("Need a new confirmation email?");
  });
});
