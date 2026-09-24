import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";

const usePathname = vi.fn<() => string>();

vi.mock("next/navigation", () => ({
  usePathname: () => usePathname(),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: ComponentProps<"a"> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import { MobileNav } from "@/components/mobile-nav";
import { NAV } from "@/lib/nav-config";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("MobileNav", () => {
  it("starts closed — the dialog panel is inert and translated off-screen", () => {
    usePathname.mockReturnValue("/dashboard");
    render(<MobileNav entries={NAV} />);

    expect(screen.getByRole("button", { name: "Open navigation menu" })).toBeInTheDocument();
    const dialog = screen.getByRole("dialog", { name: "Primary navigation", hidden: true });
    expect(dialog).toHaveAttribute("inert");
    expect(dialog.className).toContain("-translate-x-full");
  });

  it("opens to the root list — categories plus the direct Dashboard/Reports/Settings links", async () => {
    usePathname.mockReturnValue("/dashboard");
    const user = userEvent.setup();
    render(<MobileNav entries={NAV} />);

    await user.click(screen.getByRole("button", { name: "Open navigation menu" }));

    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Payroll/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Reports" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Settings" })).toBeInTheDocument();
    // Root view has no destinations drilled into yet.
    expect(screen.queryByRole("link", { name: "Employees" })).not.toBeInTheDocument();
  });

  it("drills into a category on tap, and Back to main menu returns to the root list", async () => {
    usePathname.mockReturnValue("/dashboard");
    const user = userEvent.setup();
    render(<MobileNav entries={NAV} />);

    await user.click(screen.getByRole("button", { name: "Open navigation menu" }));
    await user.click(screen.getByRole("button", { name: /^Payroll/ }));

    expect(screen.getByRole("link", { name: "Employees" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "WPS / SIF Export" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to main menu" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Back to main menu" }));

    expect(screen.getByRole("button", { name: /^Payroll/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Employees" })).not.toBeInTheDocument();
  });

  it("reopening while already on a route inside a category drills straight in with that destination current", async () => {
    usePathname.mockReturnValue("/employees");
    const user = userEvent.setup();
    render(<MobileNav entries={NAV} />);

    await user.click(screen.getByRole("button", { name: "Open navigation menu" }));

    expect(screen.getByRole("button", { name: "Back to main menu" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Employees" })).toHaveAttribute("aria-current", "page");
  });

  it("closes when Escape is pressed", async () => {
    usePathname.mockReturnValue("/dashboard");
    const user = userEvent.setup();
    render(<MobileNav entries={NAV} />);

    await user.click(screen.getByRole("button", { name: "Open navigation menu" }));
    const dialog = screen.getByRole("dialog", { name: "Primary navigation", hidden: true });
    expect(dialog).not.toHaveAttribute("inert");

    await user.keyboard("{Escape}");
    expect(dialog).toHaveAttribute("inert");
  });

  it("closes when the close button is clicked", async () => {
    usePathname.mockReturnValue("/dashboard");
    const user = userEvent.setup();
    render(<MobileNav entries={NAV} />);

    await user.click(screen.getByRole("button", { name: "Open navigation menu" }));
    const dialog = screen.getByRole("dialog", { name: "Primary navigation", hidden: true });

    await user.click(screen.getByRole("button", { name: "Close navigation menu" }));
    expect(dialog).toHaveAttribute("inert");
  });
});
