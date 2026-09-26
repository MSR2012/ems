import { Suspense, useEffect, useState, type ComponentType } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { LoadingState } from '@/shared/ui/feedback';
import {
  IconClose, IconDashboard, IconInbox, IconMail, IconMenu, IconPlug, IconSettings,
} from '@/shared/ui/icons';
import { UserMenu } from '@/features/auth/UserMenu';
import { SyncIndicator } from '@/features/gmail-connection/SyncIndicator';

const NAV: { to: string; label: string; icon: ComponentType<{ className?: string }>; end?: boolean; also?: string[] }[] = [
  { to: '/', label: 'Dashboard', icon: IconDashboard, end: true },
  { to: '/inbox', label: 'Inbox', icon: IconInbox, also: ['/emails/', '/threads/'] },
  { to: '/integrations', label: 'Integrations', icon: IconPlug },
  { to: '/settings', label: 'Settings', icon: IconSettings },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const { pathname } = useLocation();
  return (
    <ul className="space-y-1">
      {NAV.map(({ to, label, icon: Icon, end, also }) => (
        <li key={to}>
          <NavLink
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive: active }) => {
              const isActive = active || !!also?.some((p) => pathname.startsWith(p));
              return `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`;
            }}
          >
            <Icon className="h-5 w-5" /> {label}
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white">
        <IconMail className="h-4 w-4" />
      </span>
      <span className="text-base font-semibold tracking-tight">Inbox AI</span>
    </div>
  );
}

export function AppLayout() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-slate-200 bg-white px-4 py-5 lg:flex">
        <Brand />
        <nav className="mt-8 flex-1" aria-label="Main navigation">
          <NavItems />
          <SyncIndicator />
        </nav>
        <UserMenu />
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur lg:hidden">
        <Brand />
        <button type="button" className="btn-ghost px-2" aria-label="Open menu" aria-expanded={open} onClick={() => setOpen(true)}>
          <IconMenu />
        </button>
      </header>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85%] flex-col bg-white px-4 py-5 shadow-xl">
            <div className="flex items-center justify-between">
              <Brand />
              <button type="button" className="btn-ghost px-2" aria-label="Close menu" onClick={() => setOpen(false)}>
                <IconClose />
              </button>
            </div>
            <nav className="mt-8 flex-1" aria-label="Main navigation">
              <NavItems onNavigate={() => setOpen(false)} />
              <SyncIndicator />
            </nav>
            <UserMenu />
          </div>
        </div>
      )}

      <main className="lg:pl-60">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Suspense fallback={<LoadingState />}>
            <Outlet />
          </Suspense>
        </div>
      </main>
    </div>
  );
}
