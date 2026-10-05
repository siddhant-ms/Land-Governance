'use client';
import clsx from 'clsx';
import { Landmark, LogOut, User as UserIcon } from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { can, useAuth } from '@/lib/auth';
import { Badge } from './ui';

const NAV = [
  { href: '/research', label: 'Research' }, { href: '/map', label: 'Map' }, { href: '/simulation', label: 'Scenario Lab' },
  { href: '/workspace', label: 'Workspace' },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { user, role, logout, loading } = useAuth();
  const nav = can.review(role) || can.admin(role) ? [...NAV, { href: '/admin', label: 'Admin' }] : NAV;
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-ink-700 bg-ink text-white">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
          <Link href="/" className="flex items-center gap-2 font-serif text-lg font-semibold"><Landmark className="h-5 w-5 text-brand-100" />
            <span>Land Governance <span className="text-brand-100">Evidence Platform</span></span></Link>
          <nav className="ml-4 hidden gap-1 md:flex" aria-label="Primary">
            {nav.map((n) => <Link key={n.href} href={n.href} className={clsx('rounded px-3 py-1.5 text-sm transition hover:bg-white/10', path.startsWith(n.href) && 'bg-white/15')}>{n.label}</Link>)}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            {loading ? null : user ? (<>
              <span className="hidden items-center gap-1.5 sm:flex"><UserIcon className="h-4 w-4 text-brand-100" />{user.name}<Badge tone="brand" className="!bg-white/15 !text-white">{user.role}</Badge></span>
              <button aria-label="Sign out" className="rounded p-1.5 hover:bg-white/10" onClick={() => { logout(); router.push('/'); }}><LogOut className="h-4 w-4" /></button></>)
              : <Link href="/login" className="rounded bg-white/15 px-3 py-1.5 hover:bg-white/25">Sign in</Link>}
          </div>
        </div>
        <div className="border-t border-white/10 bg-saffron-50 py-1 text-center text-[11px] font-medium text-ink-700">
          Prototype for SIH 2026 (SIH26019). The seeded corpus, indicators and model coefficients are <strong>DEMO / SYNTHETIC</strong> — not official statistics.
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8">{children}</main>
      <footer className="border-t border-ink-100 py-4 text-center text-xs text-ink-400">Decision support, not automated decision-making. Model outputs are scenario estimates, not predictions.</footer>
    </div>);
}
