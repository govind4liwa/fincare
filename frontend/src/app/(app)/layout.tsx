"use client";

import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { EntityProvider } from "@/lib/entity-context";
import { EntitySwitcher } from "@/components/entity-switcher";
import { SidebarNav } from "@/components/sidebar-nav";
import { MobileNav } from "@/components/mobile-nav";
import { NAV, filterNavByAccess } from "@/lib/nav-config";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, logout } = useAuth();

  // Every destination below is readable by any authenticated entity member
  // today (see apps.users.permissions.ReadAnyWriteRole — writes are
  // role-gated per action, not whole pages), so nothing is filtered out yet.
  // This is the hook a future page-level authorization layer plugs into.
  const entries = useMemo(() => filterNavByAccess(NAV), []);

  // `useAuth`'s isAuthenticated reads localStorage via useSyncExternalStore,
  // which reports its `false` server snapshot on the render that matches
  // SSR output before resolving to the real client value one render later.
  // Redirecting straight off that transient render bounced every
  // authenticated reload/direct load to /login despite valid tokens — so
  // the redirect is deferred a tick and cancelled if isAuthenticated has
  // already resolved to true by the time it would fire.
  useEffect(() => {
    if (isAuthenticated) return;
    const id = setTimeout(() => router.replace("/login"), 0);
    return () => clearTimeout(id);
  }, [isAuthenticated, router]);

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        Loading…
      </div>
    );
  }

  return (
    <EntityProvider>
      <div className="flex min-h-screen">
        {/* Sidebar (desktop) */}
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-border bg-card md:flex">
          <div className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-4">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground font-bold">
              F
            </div>
            <span className="font-semibold">FinCare</span>
          </div>
          <SidebarNav entries={entries} />
        </aside>

        {/* Main column */}
        <div className="flex flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card px-4">
            <div className="flex items-center gap-3">
              <MobileNav entries={entries} />
              <EntitySwitcher />
            </div>
            <button
              onClick={logout}
              className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </header>
          <main className="flex-1 p-6">{children}</main>
        </div>
      </div>
    </EntityProvider>
  );
}
