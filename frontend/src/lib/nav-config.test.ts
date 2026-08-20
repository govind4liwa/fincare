import { describe, expect, it } from "vitest";
import {
  NAV,
  filterNavByAccess,
  findActiveGroupId,
  isGroup,
  isNavLeafActive,
  type NavEntry,
} from "@/lib/nav-config";

describe("isNavLeafActive", () => {
  it("matches an exact route", () => {
    expect(isNavLeafActive("/employees", "/employees")).toBe(true);
  });

  it("matches a nested route under the destination", () => {
    expect(isNavLeafActive("/employees/123/edit", "/employees")).toBe(true);
  });

  it("does not match an unrelated route that merely shares a prefix", () => {
    expect(isNavLeafActive("/employees-archive", "/employees")).toBe(false);
  });
});

describe("findActiveGroupId", () => {
  it("finds the group containing the active route (Payroll for /employees)", () => {
    expect(findActiveGroupId("/employees", NAV)).toBe("payroll");
  });

  it("finds the group for a nested child route", () => {
    expect(findActiveGroupId("/employees/123/edit", NAV)).toBe("payroll");
  });

  it("returns null for a direct-link route (Dashboard is not inside a group)", () => {
    expect(findActiveGroupId("/dashboard", NAV)).toBeNull();
  });

  it("returns null for an unknown route", () => {
    expect(findActiveGroupId("/does-not-exist", NAV)).toBeNull();
  });
});

describe("NAV structure — retains all 29 destinations", () => {
  it("has exactly 29 leaf destinations across direct links and group children", () => {
    const count = NAV.reduce((total, entry) => total + (isGroup(entry) ? entry.children.length : 1), 0);
    expect(count).toBe(29);
  });

  it("has no duplicate hrefs", () => {
    const hrefs: string[] = [];
    for (const entry of NAV) {
      if (isGroup(entry)) hrefs.push(...entry.children.map((c) => c.href));
      else hrefs.push(entry.href);
    }
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });

  it("keeps Dashboard, Reports, and Settings as direct links, not groups", () => {
    const direct = NAV.filter((e): e is Extract<NavEntry, { kind: "link" }> => e.kind === "link");
    expect(direct.map((e) => e.href).sort()).toEqual(["/dashboard", "/reports", "/settings"]);
  });

  it("gives every group at least one child (no accidental one-item or empty groups collapse the design)", () => {
    for (const entry of NAV) {
      if (isGroup(entry)) expect(entry.children.length).toBeGreaterThan(0);
    }
  });
});

describe("filterNavByAccess", () => {
  it("returns everything unfiltered by default (today's actual authorization model)", () => {
    const result = filterNavByAccess(NAV);
    const originalCount = NAV.reduce((n, e) => n + (isGroup(e) ? e.children.length : 1), 0);
    const resultCount = result.reduce((n, e) => n + (isGroup(e) ? e.children.length : 1), 0);
    expect(resultCount).toBe(originalCount);
  });

  it("drops a direct link whose permission is denied", () => {
    const entries: NavEntry[] = [
      { kind: "link", id: "a", label: "A", href: "/a", icon: NAV[0].icon, permission: "secret" },
      { kind: "link", id: "b", label: "B", href: "/b", icon: NAV[0].icon },
    ];
    const result = filterNavByAccess(entries, () => false);
    expect(result.map((e) => e.id)).toEqual(["b"]);
  });

  it("drops only the denied children of a group, keeping the allowed ones", () => {
    const entries: NavEntry[] = [
      {
        kind: "group",
        id: "g",
        label: "G",
        icon: NAV[0].icon,
        children: [
          { id: "x", label: "X", href: "/x", icon: NAV[0].icon, permission: "denied" },
          { id: "y", label: "Y", href: "/y", icon: NAV[0].icon },
        ],
      },
    ];
    const result = filterNavByAccess(entries, (p) => p !== "denied");
    expect(result).toHaveLength(1);
    expect((result[0] as Extract<NavEntry, { kind: "group" }>).children.map((c) => c.id)).toEqual([
      "y",
    ]);
  });

  it("suppresses a group entirely when none of its children pass", () => {
    const entries: NavEntry[] = [
      {
        kind: "group",
        id: "g",
        label: "G",
        icon: NAV[0].icon,
        children: [{ id: "x", label: "X", href: "/x", icon: NAV[0].icon, permission: "denied" }],
      },
      { kind: "link", id: "b", label: "B", href: "/b", icon: NAV[0].icon },
    ];
    const result = filterNavByAccess(entries, () => false);
    expect(result.map((e) => e.id)).toEqual(["b"]);
  });
});
