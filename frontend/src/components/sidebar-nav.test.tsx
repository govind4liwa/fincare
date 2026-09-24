import { cleanup, render, screen, within } from "@testing-library/react";
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

import { SidebarNav } from "@/components/sidebar-nav";
import { NAV } from "@/lib/nav-config";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SidebarNav", () => {
  it("renders every group collapsed and every direct link, with no group expanded on a direct-link route", () => {
    usePathname.mockReturnValue("/dashboard");
    render(<SidebarNav entries={NAV} />);

    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
    for (const entry of NAV) {
      if (entry.kind === "group") {
        expect(screen.getByRole("button", { name: entry.label })).toHaveAttribute(
          "aria-expanded",
          "false",
        );
      }
    }
  });

  it("auto-expands the group containing the active route, with the child marked aria-current", () => {
    usePathname.mockReturnValue("/employees");
    render(<SidebarNav entries={NAV} />);

    expect(screen.getByRole("button", { name: "Payroll" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "Employees" })).toHaveAttribute("aria-current", "page");
  });

  it("expands a group on click and toggles it closed on a second click", async () => {
    usePathname.mockReturnValue("/dashboard");
    const user = userEvent.setup();
    render(<SidebarNav entries={NAV} />);

    const header = screen.getByRole("button", { name: "General Ledger" });
    expect(header).toHaveAttribute("aria-expanded", "false");

    await user.click(header);
    expect(header).toHaveAttribute("aria-expanded", "true");

    await user.click(header);
    expect(header).toHaveAttribute("aria-expanded", "false");
  });

  it("is a single-open accordion — opening one group closes the previously open one", async () => {
    usePathname.mockReturnValue("/dashboard");
    const user = userEvent.setup();
    render(<SidebarNav entries={NAV} />);

    const gl = screen.getByRole("button", { name: "General Ledger" });
    const payroll = screen.getByRole("button", { name: "Payroll" });

    await user.click(gl);
    expect(gl).toHaveAttribute("aria-expanded", "true");

    await user.click(payroll);
    expect(payroll).toHaveAttribute("aria-expanded", "true");
    expect(gl).toHaveAttribute("aria-expanded", "false");
  });

  it("supports keyboard operation — Enter and Space toggle a focused group header", async () => {
    usePathname.mockReturnValue("/dashboard");
    const user = userEvent.setup();
    render(<SidebarNav entries={NAV} />);

    const header = screen.getByRole("button", { name: "General Ledger" });
    header.focus();
    expect(header).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(header).toHaveAttribute("aria-expanded", "true");

    await user.keyboard(" ");
    expect(header).toHaveAttribute("aria-expanded", "false");
  });

  it("filters to the entries it's given — an empty-group-suppressed list omits that group entirely", () => {
    usePathname.mockReturnValue("/dashboard");
    const restricted = NAV.filter((e) => e.id !== "payroll");
    render(<SidebarNav entries={restricted} />);

    expect(screen.queryByRole("button", { name: "Payroll" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "General Ledger" })).toBeInTheDocument();
  });

  it("scopes each group's children to that group's own disclosure region", () => {
    usePathname.mockReturnValue("/dashboard");
    render(<SidebarNav entries={NAV} />);

    const payrollHeader = screen.getByRole("button", { name: "Payroll" });
    const panel = document.getElementById(payrollHeader.getAttribute("aria-controls")!);
    expect(panel).not.toBeNull();
    expect(within(panel!).getByRole("link", { name: "Employees" })).toBeInTheDocument();
  });
});
