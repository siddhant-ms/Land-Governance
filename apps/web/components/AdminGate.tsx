'use client';
import { can, useAuth } from '@/lib/auth';
import { ErrorState, LoginGate } from './ui';

export function AdminGate({ children, need = 'review' }: { children: React.ReactNode; need?: 'review' | 'admin' }) {
  const { role, loading } = useAuth();
  if (loading) return null;
  if (role === 'public') return <LoginGate what="The admin console" />;
  if (!(need === 'admin' ? can.admin(role) : can.review(role))) return <ErrorState error={new Error('Your role does not have access to this area.')} />;
  return <>{children}</>;
}
