"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { findActiveGroupId, isGroup, isNavLeafActive, type NavEntry } from "@/lib/nav-config";

const linkClass =
  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";
const inactiveClass = "text-muted-foreground hover:bg-accent hover:text-accent-foreground";
const activeClass = "bg-primary/10 font-semibold text-primary";

/** Desktop accordion sidebar: single-open groups, auto-expanded to the active route. */
export function SidebarNav({ entries }: { entries: NavEntry[] }) {
  const pathname = usePathname();
  // Keying by pathname remounts the panel (and its openGroupId state) fresh
  // on every navigation — including refresh, direct URL access, and browser
  // back/forward — so the active route's group is always the one expanded,
  // while a manual toggle still sticks between re-renders on the same route.
  return <SidebarNavPanel key={pathname} pathname={pathname} entries={entries} />;
}

function SidebarNavPanel({ pathname, entries }: { pathname: string; entries: NavEntry[] }) {
  const [openGroupId, setOpenGroupId] = useState<string | null>(() =>
    findActiveGroupId(pathname, entries),
  );

  return (
    <nav aria-label="Primary" className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
      {entries.map((entry) => {
        if (!isGroup(entry)) {
          const active = isNavLeafActive(pathname, entry.href);
          return (
            <Link
              key={entry.id}
              href={entry.href}
              aria-current={active ? "page" : undefined}
              className={cn("font-medium", linkClass, active ? activeClass : inactiveClass)}
            >
              <entry.icon className="h-4 w-4 shrink-0" />
              <span className="truncate" title={entry.label}>
                {entry.label}
              </span>
            </Link>
          );
        }

        const isOpen = openGroupId === entry.id;
        const hasActiveChild = entry.children.some((child) => isNavLeafActive(pathname, child.href));
        const panelId = `nav-group-panel-${entry.id}`;

        return (
          <div key={entry.id} className="flex flex-col">
            <button
              type="button"
              aria-expanded={isOpen}
              aria-controls={panelId}
              onClick={() => setOpenGroupId(isOpen ? null : entry.id)}
              className={cn(
                "font-medium",
                linkClass,
                "w-full",
                hasActiveChild ? "font-semibold text-primary" : inactiveClass,
              )}
            >
              <entry.icon className="h-4 w-4 shrink-0" />
              <span className="flex-1 truncate text-left" title={entry.label}>
                {entry.label}
              </span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 shrink-0 transition-transform duration-200 motion-reduce:transition-none",
                  isOpen && "rotate-180",
                )}
                aria-hidden="true"
              />
            </button>
            <div
              id={panelId}
              inert={!isOpen}
              className={cn(
                "grid transition-[grid-template-rows] duration-200 motion-reduce:transition-none",
                isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
              )}
            >
              <div className="overflow-hidden">
                <div role="group" aria-label={entry.label} className="flex flex-col gap-1 py-1 pl-4">
                  {entry.children.map((child) => {
                    const active = isNavLeafActive(pathname, child.href);
                    return (
                      <Link
                        key={child.id}
                        href={child.href}
                        aria-current={active ? "page" : undefined}
                        className={cn(linkClass, "py-1.5", active ? activeClass : inactiveClass)}
                      >
                        <child.icon className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate" title={child.label}>
                          {child.label}
                        </span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </nav>
  );
}
