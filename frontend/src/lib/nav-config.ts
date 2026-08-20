import type { LucideIcon } from "lucide-react";
import {
  ArrowLeftRight,
  BarChart3,
  Banknote,
  BookOpen,
  Calculator,
  CalendarClock,
  CreditCard,
  FileMinus2,
  FilePlus2,
  FileSpreadsheet,
  FileText,
  HandCoins,
  HandHeart,
  IdCard,
  Landmark,
  LayoutDashboard,
  ListTree,
  MapPin,
  Percent,
  PiggyBank,
  Receipt,
  ReceiptText,
  Scale,
  ScrollText,
  Settings,
  Smartphone,
  TrendingDown,
  Truck,
  Umbrella,
  Users,
  Wallet,
} from "lucide-react";

/**
 * A permission/feature-flag key a future page-level authorization layer
 * could check before showing an item. Unset today everywhere: FinCare's API
 * grants read access to every one of these destinations to any authenticated
 * entity member (see `apps.users.permissions.ReadAnyWriteRole` — writes are
 * role-gated per action, not whole pages), so there is nothing real to hide
 * yet. `filterNavByAccess` treats an item with no `permission` as visible to
 * everyone, which matches that today.
 */
export type NavPermission = string;

export type NavLeaf = {
  id: string;
  label: string;
  href: string;
  icon: LucideIcon;
  permission?: NavPermission;
};

export type NavGroup = {
  kind: "group";
  id: string;
  label: string;
  icon: LucideIcon;
  children: NavLeaf[];
  permission?: NavPermission;
};

export type NavLink = NavLeaf & { kind: "link" };

export type NavEntry = NavLink | NavGroup;

export const NAV: NavEntry[] = [
  { kind: "link", id: "dashboard", label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  {
    kind: "group",
    id: "general-ledger",
    label: "General Ledger",
    icon: BookOpen,
    children: [
      { id: "accounts", label: "Chart of Accounts", href: "/accounts", icon: BookOpen },
      { id: "vouchers", label: "Vouchers", href: "/vouchers", icon: Receipt },
      { id: "periods", label: "Accounting Periods", href: "/periods", icon: CalendarClock },
    ],
  },
  {
    kind: "group",
    id: "receivables-payables",
    label: "Receivables & Payables",
    icon: ArrowLeftRight,
    children: [
      { id: "parties", label: "Customers & Suppliers", href: "/parties", icon: Users },
      { id: "invoices", label: "Sales Invoices", href: "/invoices", icon: FileText },
      { id: "credit-notes", label: "Credit Notes", href: "/credit-notes", icon: FileMinus2 },
      { id: "bills", label: "Purchase Bills", href: "/bills", icon: ReceiptText },
      { id: "debit-notes", label: "Debit Notes", href: "/debit-notes", icon: FilePlus2 },
    ],
  },
  {
    kind: "group",
    id: "banking-reconciliation",
    label: "Banking & Reconciliation",
    icon: Landmark,
    children: [
      { id: "banking", label: "Bank Accounts", href: "/banking", icon: Landmark },
      { id: "reconcile", label: "Reconciliation", href: "/reconcile", icon: Scale },
    ],
  },
  {
    kind: "group",
    id: "fleet-operations",
    label: "Fleet Operations",
    icon: Truck,
    children: [
      { id: "fleet", label: "Fleet & Drivers", href: "/fleet", icon: Truck },
      { id: "platforms", label: "Platforms", href: "/platforms", icon: Smartphone },
      { id: "contracts", label: "Contracts", href: "/contracts", icon: ScrollText },
      { id: "trips", label: "Trip Register", href: "/trips", icon: MapPin },
    ],
  },
  {
    kind: "group",
    id: "driver-accounts",
    label: "Driver Accounts",
    icon: Wallet,
    children: [
      { id: "advances", label: "Driver Advances", href: "/advances", icon: Wallet },
      { id: "settlements", label: "Driver Settlements", href: "/settlements", icon: HandCoins },
      {
        id: "driver-clearings",
        label: "Driver Clearings",
        href: "/driver-clearings",
        icon: HandHeart,
      },
    ],
  },
  {
    kind: "group",
    id: "vehicle-assets-finance",
    label: "Vehicle Assets & Finance",
    icon: CreditCard,
    children: [
      { id: "loans", label: "Vehicle Loans", href: "/loans", icon: CreditCard },
      { id: "depreciation", label: "Vehicle Depreciation", href: "/depreciation", icon: TrendingDown },
    ],
  },
  {
    kind: "group",
    id: "tax-compliance",
    label: "Tax & Compliance",
    icon: Percent,
    children: [
      { id: "vat-returns", label: "VAT Returns", href: "/vat-returns", icon: Percent },
      {
        id: "corporate-tax-returns",
        label: "Corporate Tax",
        href: "/corporate-tax-returns",
        icon: Calculator,
      },
    ],
  },
  {
    kind: "group",
    id: "payroll",
    label: "Payroll",
    icon: Banknote,
    children: [
      { id: "employees", label: "Employees", href: "/employees", icon: IdCard },
      { id: "salary-components", label: "Salary Components", href: "/salary-components", icon: ListTree },
      { id: "payroll-advances", label: "Salary Advances", href: "/payroll-advances", icon: PiggyBank },
      { id: "payroll-runs", label: "Payroll Runs", href: "/payroll-runs", icon: Banknote },
      { id: "wps-batches", label: "WPS / SIF Export", href: "/wps-batches", icon: FileSpreadsheet },
      { id: "gratuity-leave", label: "Gratuity & Leave", href: "/gratuity-leave", icon: Umbrella },
    ],
  },
  { kind: "link", id: "reports", label: "Reports", href: "/reports", icon: BarChart3 },
  { kind: "link", id: "settings", label: "Settings", href: "/settings", icon: Settings },
];

export function isGroup(entry: NavEntry): entry is NavGroup {
  return entry.kind === "group";
}

export function isNavLeafActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** The group (if any) whose child matches `pathname` — used to auto-expand it. */
export function findActiveGroupId(pathname: string, entries: NavEntry[] = NAV): string | null {
  for (const entry of entries) {
    if (isGroup(entry) && entry.children.some((child) => isNavLeafActive(pathname, child.href))) {
      return entry.id;
    }
  }
  return null;
}

/**
 * Filters nav entries by `hasAccess`, dropping any group left with no
 * visible children. Defaults to "everything visible", matching FinCare's
 * actual authorization model today (see the `permission` doc comment above)
 * — this is the extension point a future page-level authorization layer
 * would plug a real check into, not a currently-active restriction.
 */
export function filterNavByAccess(
  entries: NavEntry[],
  hasAccess: (permission: NavPermission) => boolean = () => true,
): NavEntry[] {
  const isVisible = (permission?: NavPermission) => !permission || hasAccess(permission);
  const result: NavEntry[] = [];
  for (const entry of entries) {
    if (!isGroup(entry)) {
      if (isVisible(entry.permission)) result.push(entry);
      continue;
    }
    if (!isVisible(entry.permission)) continue;
    const children = entry.children.filter((child) => isVisible(child.permission));
    if (children.length > 0) result.push({ ...entry, children });
  }
  return result;
}
