'use client';
import clsx from 'clsx';
import Link from 'next/link';
import { AlertTriangle, FileWarning, Inbox, Loader2, Lock, ShieldAlert } from 'lucide-react';
import type { ReactNode } from 'react';
import { ApiError } from '@/lib/api';

export function Button({ variant = 'primary', size = 'md', className, ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; size?: 'sm' | 'md' }) {
  return <button {...p} className={clsx('inline-flex items-center justify-center gap-2 rounded-md font-medium transition disabled:cursor-not-allowed disabled:opacity-50',
    size === 'sm' ? 'px-2.5 py-1.5 text-xs' : 'px-4 py-2 text-sm',
    variant === 'primary' && 'bg-brand text-white hover:bg-brand-700',
    variant === 'secondary' && 'border border-ink-200 bg-white text-ink hover:bg-ink-50',
    variant === 'ghost' && 'text-ink-500 hover:bg-ink-100',
    variant === 'danger' && 'bg-alert text-white hover:opacity-90', className)} />;
}
export function LinkButton({ href, children, variant = 'primary', className }: { href: string; children: ReactNode; variant?: 'primary' | 'secondary'; className?: string }) {
  return <Link href={href} className={clsx('inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition',
    variant === 'primary' ? 'bg-brand text-white hover:bg-brand-700' : 'border border-ink-200 bg-white hover:bg-ink-50', className)}>{children}</Link>;
}
export const Card = ({ className, children }: { className?: string; children: ReactNode }) => <div className={clsx('card', className)}>{children}</div>;
export const Badge = ({ tone = 'neutral', children, className }: { tone?: 'neutral' | 'brand' | 'saffron' | 'alert'; children: ReactNode; className?: string }) => (
  <span className={clsx('inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide',
    tone === 'neutral' && 'bg-ink-100 text-ink-500', tone === 'brand' && 'bg-brand-100 text-brand-700',
    tone === 'saffron' && 'bg-saffron-100 text-saffron', tone === 'alert' && 'bg-alert-50 text-alert', className)}>{children}</span>);
export const DemoBadge = ({ label = 'DEMO DATA', title }: { label?: string; title?: string }) => (
  <span title={title ?? 'Synthetic/authored for the prototype. Not an official source or statistic.'} className="inline-flex items-center rounded border border-saffron/40 bg-saffron-50 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-saffron">{label}</span>);
export const OfficialBadge = () => <Badge tone="brand">Official source</Badge>;
export const Spinner = ({ label = 'Loading…' }: { label?: string }) => (
  <div role="status" className="flex items-center gap-2 py-8 text-sm text-ink-400"><Loader2 className="h-4 w-4 animate-spin" />{label}</div>);
export const Skeleton = ({ className }: { className?: string }) => <div className={clsx('animate-pulse rounded bg-ink-100', className)} />;

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error instanceof ApiError ? error : null;
  const restricted = e?.code === 'RESTRICTED_DOCUMENT' || e?.code === 'RESTRICTED_DATASET';
  const Icon = restricted ? Lock : e?.status === 401 ? ShieldAlert : AlertTriangle;
  return (
    <div role="alert" className="card flex gap-3 border-alert/20 p-4">
      <Icon className={clsx('mt-0.5 h-5 w-5 shrink-0', restricted ? 'text-saffron' : 'text-alert')} />
      <div className="text-sm">
        <p className="font-medium">{restricted ? 'Restricted' : e?.status === 401 ? 'Sign in required' : 'Something went wrong'}</p>
        <p className="mt-0.5 text-ink-500">{e?.message ?? (error instanceof Error ? error.message : 'Unexpected error.')}</p>
        {e?.status === 401 && <Link className="mt-2 inline-block text-brand underline" href="/login">Go to sign in</Link>}
        {onRetry && <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>Try again</Button>}
      </div>
    </div>);
}
export const EmptyState = ({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) => (
  <div className="card flex flex-col items-center gap-2 px-6 py-10 text-center">
    {icon ?? <Inbox className="h-7 w-7 text-ink-300" />}<p className="font-serif text-lg">{title}</p>
    <div className="max-w-md text-sm text-ink-500">{children}</div></div>);
export const Notice = ({ tone = 'saffron', children }: { tone?: 'saffron' | 'brand' | 'alert'; children: ReactNode }) => (
  <div className={clsx('flex gap-2 rounded-md border px-3 py-2 text-xs', tone === 'saffron' && 'border-saffron/30 bg-saffron-50 text-ink-700',
    tone === 'brand' && 'border-brand/20 bg-brand-50 text-ink-700', tone === 'alert' && 'border-alert/30 bg-alert-50 text-ink-700')}>
    <FileWarning className="mt-0.5 h-3.5 w-3.5 shrink-0" /><div>{children}</div></div>);

export function PageHeader({ title, sub, actions, eyebrow }: { title: string; sub?: ReactNode; actions?: ReactNode; eyebrow?: string }) {
  return (<div className="mb-6 flex flex-wrap items-end justify-between gap-3">
    <div>{eyebrow && <p className="label mb-1 text-brand">{eyebrow}</p>}<h1 className="text-3xl font-semibold">{title}</h1>{sub && <p className="mt-1 max-w-3xl text-sm text-ink-500">{sub}</p>}</div>
    {actions}</div>);
}
export const Stat = ({ value, label, hint }: { value: ReactNode; label: string; hint?: string }) => (
  <div><p className="font-serif text-3xl font-semibold tabular-nums">{value}</p><p className="label mt-1">{label}</p>{hint && <p className="mt-0.5 text-xs text-ink-400">{hint}</p>}</div>);
export const Select = ({ className, ...p }: React.SelectHTMLAttributes<HTMLSelectElement>) => (
  <select {...p} className={clsx('rounded-md border border-ink-200 bg-white px-2.5 py-1.5 text-sm', className)} />);
export const Input = ({ className, ...p }: React.InputHTMLAttributes<HTMLInputElement>) => (
  <input {...p} className={clsx('w-full rounded-md border border-ink-200 bg-white px-3 py-2 text-sm placeholder:text-ink-300', className)} />);

export function LoginGate({ what }: { what: string }) {
  return <EmptyState title="Sign in to continue" icon={<Lock className="h-7 w-7 text-ink-300" />}>
    {what} requires an account. Demo accounts are listed on the sign-in page.<div className="mt-4"><LinkButton href="/login">Sign in</LinkButton></div></EmptyState>;
}
