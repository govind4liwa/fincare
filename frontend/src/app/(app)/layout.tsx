"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  CreditCard,
  FileMinus2,
  FilePlus2,
  FileText,
  HandCoins,
  Landmark,
  LayoutDashboard,
  LogOut,
  Receipt,
  ReceiptText,
  Scale,
  Settings,
  Truck,
  Users,
  Wallet,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { EntityProvider } from "@/lib/entity-context";
import { EntitySwitcher } from "@/components/entity-switcher";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/accounts", label: "Chart of Accounts", icon: BookOpen },
  { href: "/vouchers", label: "Vouchers", icon: Receipt },
  { href: "/invoices", label: "Sales Invoices", icon: FileText },
  { href: "/bills", label: "Purchase Bills", icon: ReceiptText },
  { href: "/credit-notes", label: "Credit Notes", icon: FileMinus2 },
  { href: "/debit-notes", label: "Debit Notes", icon: FilePlus2 },
  { href: "/parties", label: "Customers & Suppliers", icon: Users },
  { href: "/fleet", label: "Fleet & Drivers", icon: Truck },
  { href: "/advances", label: "Driver Advances", icon: Wallet },
  { href: "/settlements", label: "Driver Settlements", icon: HandCoins },
  { href: "/loans", label: "Vehicle Loans", icon: CreditCard },
  { href: "/banking", label: "Bank Accounts", icon: Landmark },
  { href: "/reconcile", label: "Reconciliation", icon: Scale },
  { href: "/reports", label: "Reports", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, logout } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) router.replace("/login");
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
        {/* Sidebar */}
        <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-card md:flex">
          <div className="flex h-14 items-center gap-2 border-b border-border px-4">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground font-bold">
              F
            </div>
            <span className="font-semibold">FinCare</span>
          </div>
          <nav className="flex flex-1 flex-col gap-1 p-3">
            {NAV.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || pathname.startsWith(`${href}/`);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </Link>
              );
            })}
          </nav>
        </aside>

        {/* Main column */}
        <div className="flex flex-1 flex-col">
          <header className="flex h-14 items-center justify-between border-b border-border bg-card px-4">
            <EntitySwitcher />
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
