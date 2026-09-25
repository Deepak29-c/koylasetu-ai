"use client";

import {
  ClipboardCheck,
  Cloud,
  FilePlus2,
  FileText,
  Files,
  Gauge,
  House,
  Inbox,
  Languages,
  LogOut,
  Menu,
  MessageSquareText,
  ScrollText,
  ShieldCheck,
  Upload,
  UserRound,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { useFocusTrap } from "@/components/ui/Dialog";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { api, ApiError, logout, type Me } from "@/lib/api";
import { cn } from "@/lib/cn";
import { errorText } from "@/lib/errors";
import { type LabelKey, setLang, useT } from "@/lib/i18n";
import { can, canSeeReports, type Permission } from "@/lib/permissions";

const MeContext = createContext<Me | null>(null);

/** The logged-in user. Only use inside pages wrapped by AppShell. */
export function useMe(): Me {
  const me = useContext(MeContext);
  if (!me) throw new Error("useMe() used outside AppShell");
  return me;
}

type NavItem = {
  href: string;
  label: LabelKey;
  icon: typeof House;
  show: (me: Me) => boolean;
  /** Indented under the item before it. */
  sub?: boolean;
};
type NavGroup = { label?: LabelKey; items: NavItem[] };

const has =
  (...p: Permission[]) =>
  (me: Me) =>
    can(me, ...p);

// Menu shows only what the user's role can open (the API checks again on every request).
const GROUPS: NavGroup[] = [
  { items: [{ href: "/", label: "home", icon: House, show: () => true }] },
  {
    label: "nav.work",
    items: [
      { href: "/ask", label: "ask", icon: MessageSquareText, show: has("ask_questions") },
      { href: "/reports", label: "reports", icon: FileText, show: canSeeReports },
      { href: "/approvals", label: "nav.approvals", icon: Inbox, show: has("approve_reports") },
      { href: "/pq-replies/new", label: "newPqReply", icon: FilePlus2, show: has("edit_reports"), sub: true },
      { href: "/monthly-reports/new", label: "newMonthlyReport", icon: FilePlus2, show: has("edit_reports"), sub: true },
      { href: "/briefing-notes/new", label: "newBriefingNote", icon: FilePlus2, show: has("edit_reports"), sub: true },
    ],
  },
  {
    label: "nav.data",
    items: [
      { href: "/upload", label: "upload", icon: Upload, show: has("upload_documents") },
      { href: "/documents", label: "documents", icon: Files, show: has("view_processing") },
      { href: "/review", label: "review", icon: ClipboardCheck, show: has("review_facts") },
    ],
  },
  {
    label: "nav.insights",
    items: [
      { href: "/topics", label: "topics", icon: Cloud, show: has("view_topics") },
      { href: "/metrics", label: "nav.metrics", icon: Gauge, show: has("view_metrics") },
    ],
  },
  {
    label: "nav.admin",
    items: [
      { href: "/admin/users", label: "users", icon: Users, show: has("manage_admin") },
      { href: "/audit", label: "auditLog", icon: ScrollText, show: has("view_audit") },
    ],
  },
];

const ALL_HREFS = [...GROUPS.flatMap((g) => g.items.map((i) => i.href)), "/profile"];

/** The menu entry for a path: the longest matching prefix, so /reports/123 lights up Reports. */
function activeHref(pathname: string): string | null {
  if (pathname === "/") return "/";
  const matches = ALL_HREFS.filter((h) => h !== "/" && (pathname === h || pathname.startsWith(`${h}/`)));
  return matches.sort((a, b) => b.length - a.length)[0] ?? null;
}

/** How long the pointer may leave the rail before it shrinks back (avoids flicker at the edge). */
const COLLAPSE_DELAY_MS = 180;

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useT();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  const loadMe = useCallback(() => {
    api<Me>("/me").then(setMe, (e: unknown) => {
      // A 401 is already taking us to /login (with ?next=) from inside api().
      // Redirecting again here would win the race and throw that ?next= away.
      if (e instanceof ApiError && e.status === 401) return;
      setError(errorText(e));
    });
  }, []);

  useEffect(loadMe, [loadMe]);

  const retryMe = () => {
    setError(null);
    loadMe();
  };

  // Close the mobile menu after navigating.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMobileOpen(false);
  }, [pathname]);

  const signOut = async () => {
    await logout();
    router.replace("/login");
  };

  const current = activeHref(pathname);

  return (
    <div className="flex min-h-dvh flex-1">
      <a
        href="#main"
        className="sr-only z-[80] rounded-full bg-surface px-4 py-2 font-semibold text-brand shadow-pop focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        {t("nav.skipToContent")}
      </a>

      <DesktopRail me={me} current={current} onSignOut={signOut} />

      {/* Mobile side menu */}
      {mobileOpen && (
        <MobileMenu onClose={() => setMobileOpen(false)}>
          <div className="absolute inset-0 bg-scrim" onClick={() => setMobileOpen(false)} aria-hidden />
          <aside
            aria-label={t("nav.main")}
            className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] animate-drawer-in flex-col bg-sidebar text-white shadow-float"
          >
            <div className="flex items-center justify-between pr-3">
              <Brand collapsed={false} />
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                aria-label={t("nav.closeMenu")}
                className="focus-on-dark rounded-full p-2 text-sidebar-text hover:bg-sidebar-hover hover:text-white"
              >
                <X size={20} aria-hidden />
              </button>
            </div>
            <SideNav me={me} current={current} collapsed={false} />
            <AccountNav me={me} current={current} collapsed={false} onSignOut={signOut} />
          </aside>
        </MobileMenu>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar me={me} onOpenMenu={() => setMobileOpen(true)} />
        <main id="main" tabIndex={-1} className="flex w-full max-w-[1680px] flex-1 flex-col px-4 py-6 focus:outline-none sm:px-6 lg:px-8 lg:py-7">
          {error && (
            <Alert
              tone="danger"
              title={t("shell.loadFailed")}
              action={
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={retryMe}>
                    {t("retry")}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={signOut}>
                    {t("logout")}
                  </Button>
                </div>
              }
            >
              {error}
            </Alert>
          )}
          {!me && !error && <PageSkeleton />}
          {me && <MeContext.Provider value={me}>{children}</MeContext.Provider>}
        </main>
        <footer className="border-t border-line px-4 py-4 text-center text-xs text-subtle sm:px-8">
          {t("appName")} · {t("tagline")} · {t("shell.official")}
        </footer>
      </div>
    </div>
  );
}

/** The phone and tablet menu: a modal panel that traps focus and closes on Escape. */
function MobileMenu({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, onClose);
  return (
    <div ref={ref} role="dialog" aria-modal="true" className="fixed inset-0 z-50 lg:hidden">
      {children}
    </div>
  );
}

/**
 * The desktop menu is a slim icon rail that opens while the pointer or keyboard focus is
 * inside it and closes again when both leave. It opens over the page, so the content never
 * shifts; the placeholder keeps the rail's width in the layout.
 */
function DesktopRail({ me, current, onSignOut }: { me: Me | null; current: string | null; onSignOut: () => void }) {
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const leaveTimer = useRef<number | null>(null);
  const expanded = hovered || focused;

  const cancelLeave = () => {
    if (leaveTimer.current !== null) window.clearTimeout(leaveTimer.current);
    leaveTimer.current = null;
  };
  useEffect(() => cancelLeave, []);

  return (
    <div className="relative hidden w-[72px] shrink-0 lg:block">
      <aside
        onMouseEnter={() => {
          cancelLeave();
          setHovered(true);
        }}
        onMouseLeave={() => {
          cancelLeave();
          leaveTimer.current = window.setTimeout(() => setHovered(false), COLLAPSE_DELAY_MS);
        }}
        onFocus={(e) => {
          // Only keyboard focus keeps the rail open; a mouse click also focuses the link,
          // and the rail should still close when the pointer leaves.
          if ((e.target as HTMLElement).matches(":focus-visible")) setFocused(true);
        }}
        onBlur={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setFocused(false);
        }}
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex flex-col overflow-hidden bg-sidebar text-white transition-[width,box-shadow] duration-200 ease-out",
          expanded ? "w-64 shadow-float" : "w-[72px]",
        )}
      >
        <Brand collapsed={!expanded} />
        <SideNav me={me} current={current} collapsed={!expanded} />
        <AccountNav me={me} current={current} collapsed={!expanded} onSignOut={onSignOut} />
      </aside>
    </div>
  );
}

function Brand({ collapsed }: { collapsed: boolean }) {
  const { t } = useT();
  return (
    <Link
      href="/"
      className={cn("focus-on-dark flex h-14 shrink-0 items-center gap-3 px-4", collapsed && "justify-center px-0")}
      aria-label={t("appName")}
    >
      <LogoMark />
      {!collapsed && (
        <span className="min-w-0 leading-tight">
          <span className="block text-[15px] font-bold tracking-tight">{t("appName")}</span>
          <span className="block text-[11px] text-sidebar-text">CMPDI · CIL</span>
        </span>
      )}
    </Link>
  );
}

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden className={cn("size-9 shrink-0", className)}>
      <rect width="64" height="64" rx="14" fill="rgb(255 255 255 / 0.1)" />
      <path d="M12 40c4-12 11-18 20-18s16 6 20 18" fill="none" stroke="var(--accent)" strokeWidth="5" strokeLinecap="round" />
      <path d="M20 40v6M32 32v14M44 40v6M10 48h44" stroke="#fff" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

function SideNav({ me, current, collapsed }: { me: Me | null; current: string | null; collapsed: boolean }) {
  const { t } = useT();
  return (
    <nav aria-label={t("nav.main")} className="flex-1 overflow-x-hidden overflow-y-auto px-3 py-2">
      {GROUPS.map((g, gi) => {
        const items = me ? g.items.filter((i) => i.show(me)) : [];
        if (!items.length) return null;
        return (
          <div key={gi} className={cn(gi > 0 && "mt-4")}>
            {g.label && <GroupLabel label={t(g.label)} collapsed={collapsed} />}
            <ul className="space-y-0.5">
              {items.map((it) => (
                <li key={it.href}>
                  <RailLink
                    href={it.href}
                    label={t(it.label)}
                    icon={it.icon}
                    active={current === it.href}
                    collapsed={collapsed}
                    sub={it.sub}
                  />
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

function GroupLabel({ label, collapsed }: { label: string; collapsed: boolean }) {
  return (
    <div className="relative mb-1 h-5">
      <span
        aria-hidden={collapsed}
        className={cn(
          "absolute inset-x-3 top-0 truncate text-[11px] font-semibold tracking-[0.08em] whitespace-nowrap text-white/55 uppercase transition-opacity duration-150",
          collapsed ? "opacity-0" : "opacity-100",
        )}
      >
        {label}
      </span>
      <span
        aria-hidden
        className={cn(
          "absolute top-2 left-4 h-px w-8 bg-white/15 transition-opacity duration-150",
          collapsed ? "opacity-100" : "opacity-0",
        )}
      />
    </div>
  );
}

const railItem =
  "focus-on-dark relative flex h-10 w-full items-center gap-3 rounded-full px-[14px] text-left text-[13px] font-medium whitespace-nowrap transition-colors";

/** One rail entry. The label stays in the DOM (for screen readers) and fades out when collapsed. */
function RailLink({
  href,
  label,
  icon: Icon,
  active,
  collapsed,
  sub,
}: {
  href: string;
  label: string;
  icon: typeof House;
  active: boolean;
  collapsed: boolean;
  sub?: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        railItem,
        sub && !collapsed && "h-9 pl-8 text-xs",
        active ? "bg-sidebar-active text-white" : "text-sidebar-text hover:bg-sidebar-hover hover:text-white",
      )}
    >
      {active && <span aria-hidden className="absolute top-1/2 left-0 h-5 w-[3px] -translate-y-1/2 rounded-full bg-accent" />}
      <Icon size={sub && !collapsed ? 16 : 18} aria-hidden className="shrink-0" />
      <RailLabel collapsed={collapsed}>{label}</RailLabel>
    </Link>
  );
}

function RailLabel({ collapsed, children }: { collapsed: boolean; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "min-w-0 truncate transition-opacity duration-150",
        collapsed ? "sr-only" : "opacity-100",
      )}
    >
      {children}
    </span>
  );
}

/** Profile and sign-out, pinned to the bottom of the menu. */
function AccountNav({
  me,
  current,
  collapsed,
  onSignOut,
}: {
  me: Me | null;
  current: string | null;
  collapsed: boolean;
  onSignOut: () => void;
}) {
  const { t } = useT();
  if (!me) return null;
  return (
    <nav aria-label={t("shell.account")} className="border-t border-white/10 px-3 py-3">
      <ul className="space-y-0.5">
        <li>
          <RailLink href="/profile" label={t("profile")} icon={UserRound} active={current === "/profile"} collapsed={collapsed} />
        </li>
        <li>
          <button
            type="button"
            onClick={onSignOut}
            className={cn(railItem, "text-sidebar-text hover:bg-sidebar-hover hover:text-white")}
          >
            <LogOut size={18} aria-hidden className="shrink-0" />
            <RailLabel collapsed={collapsed}>{t("logout")}</RailLabel>
          </button>
        </li>
      </ul>
    </nav>
  );
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
}

function TopBar({ me, onOpenMenu }: { me: Me | null; onOpenMenu: () => void }) {
  const { t, lang } = useT();

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-surface/90 px-4 backdrop-blur sm:px-6 lg:px-8">
      <button
        type="button"
        onClick={onOpenMenu}
        aria-label={t("nav.openMenu")}
        className="grid size-9 place-items-center rounded-full text-brand hover:bg-brand-soft lg:hidden"
      >
        <Menu size={20} aria-hidden />
      </button>
      <Link href="/" className="flex min-w-0 items-center gap-3 rounded-full pr-2">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-brand">
          <LogoMark className="size-9" />
        </span>
        <span className="min-w-0 leading-tight">
          <span className="block truncate text-[15px] font-bold tracking-tight text-brand">{t("appName")}</span>
          <span className="hidden truncate text-[11px] text-subtle sm:block">{t("tagline")}</span>
        </span>
      </Link>

      <div className="ml-auto flex items-center gap-3">
        <button
          type="button"
          onClick={() => setLang(lang === "en" ? "hi" : "en")}
          aria-label={t("shell.switchLanguage")}
          className="inline-flex h-9 items-center gap-2 rounded-full border border-line-strong px-3 text-xs font-semibold text-brand hover:bg-brand-tint"
        >
          <Languages size={16} aria-hidden />
          <span lang={lang === "en" ? "hi" : "en"}>{lang === "en" ? "हिंदी" : "English"}</span>
        </button>

        {me && (
          <div className="flex items-center gap-2.5">
            <span aria-hidden className="grid size-8 place-items-center rounded-full bg-brand text-xs font-bold text-white">
              {initials(me.name)}
            </span>
            <span className="hidden leading-tight sm:block">
              <span className="block text-xs font-semibold text-strong">{me.name}</span>
              <span className="flex items-center gap-1 text-[11px] text-subtle">
                <ShieldCheck size={12} aria-hidden className="text-brand" />
                {me.roles.map((r) => t(`role.${r}` as LabelKey)).join(", ")} · {me.org_unit.code}
              </span>
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
