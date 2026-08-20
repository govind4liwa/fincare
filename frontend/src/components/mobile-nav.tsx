"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft, ChevronRight, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { findActiveGroupId, isGroup, isNavLeafActive, type NavEntry, type NavGroup } from "@/lib/nav-config";

const rowClass =
  "flex items-center gap-3 rounded-md px-3 py-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";
const inactiveClass = "text-muted-foreground hover:bg-accent hover:text-accent-foreground";
const activeClass = "bg-primary/10 font-semibold text-primary";

/** Off-canvas drawer for small screens: root list drills down into one category at a time. */
export function MobileNav({ entries }: { entries: NavEntry[] }) {
  const pathname = usePathname();
  // Keying by pathname remounts the drawer (closed, root view) fresh on every
  // navigation, so selecting a destination always closes it — no effect needed.
  return <MobileNavDrawer key={pathname} pathname={pathname} entries={entries} />;
}

function MobileNavDrawer({ pathname, entries }: { pathname: string; entries: NavEntry[] }) {
  const [open, setOpen] = useState(false);
  const [viewId, setViewId] = useState<string | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Subscribes to keyboard input and moves focus while the drawer is open —
  // an external-system subscription, not a state sync, so it belongs in an effect.
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  function openDrawer() {
    // Reopen showing the category (if any) the current route belongs to, so
    // the active parent/child indicators are visible immediately.
    setViewId(findActiveGroupId(pathname, entries));
    setOpen(true);
  }

  function close() {
    setOpen(false);
    triggerRef.current?.focus();
  }

  const activeGroup = entries.find(
    (entry): entry is NavGroup => isGroup(entry) && entry.id === viewId,
  );

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={openDrawer}
        aria-label="Open navigation menu"
        className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 md:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className={cn("fixed inset-0 z-50 md:hidden", open ? "pointer-events-auto" : "pointer-events-none")}>
        <div
          aria-hidden="true"
          className={cn(
            "absolute inset-0 bg-black/40 transition-opacity duration-200 motion-reduce:transition-none",
            open ? "opacity-100" : "opacity-0",
          )}
          onClick={close}
        />
        <div
          role="dialog"
          aria-modal={open}
          aria-label="Primary navigation"
          inert={!open}
          className={cn(
            "absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-card shadow-xl transition-transform duration-200 motion-reduce:transition-none",
            open ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4">
            <span className="truncate font-semibold" title={activeGroup ? activeGroup.label : "FinCare"}>
              {activeGroup ? activeGroup.label : "FinCare"}
            </span>
            <button
              ref={closeRef}
              type="button"
              onClick={close}
              aria-label="Close navigation menu"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {activeGroup && (
            <button
              type="button"
              onClick={() => setViewId(null)}
              className="flex items-center gap-2 border-b border-border px-4 py-3 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              Back to main menu
            </button>
          )}

          <nav aria-label="Primary" className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
            {!activeGroup &&
              entries.map((entry) => {
                if (!isGroup(entry)) {
                  const active = isNavLeafActive(pathname, entry.href);
                  return (
                    <Link
                      key={entry.id}
                      href={entry.href}
                      aria-current={active ? "page" : undefined}
                      className={cn("font-medium", rowClass, active ? activeClass : inactiveClass)}
                    >
                      <entry.icon className="h-4 w-4 shrink-0" />
                      <span className="truncate" title={entry.label}>
                        {entry.label}
                      </span>
                    </Link>
                  );
                }
                const hasActiveChild = entry.children.some((child) => isNavLeafActive(pathname, child.href));
                return (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => setViewId(entry.id)}
                    className={cn(
                      "font-medium",
                      rowClass,
                      hasActiveChild ? "font-semibold text-primary" : inactiveClass,
                    )}
                  >
                    <entry.icon className="h-4 w-4 shrink-0" />
                    <span className="flex-1 truncate text-left" title={entry.label}>
                      {entry.label}
                    </span>
                    <ChevronRight className="h-4 w-4 shrink-0" aria-hidden="true" />
                  </button>
                );
              })}

            {activeGroup &&
              activeGroup.children.map((child) => {
                const active = isNavLeafActive(pathname, child.href);
                return (
                  <Link
                    key={child.id}
                    href={child.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(rowClass, active ? activeClass : inactiveClass)}
                  >
                    <child.icon className="h-4 w-4 shrink-0" />
                    <span className="truncate" title={child.label}>
                      {child.label}
                    </span>
                  </Link>
                );
              })}
          </nav>
        </div>
      </div>
    </>
  );
}
