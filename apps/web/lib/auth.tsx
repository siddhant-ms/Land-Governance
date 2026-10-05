'use client';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { Role, User } from '@sih/types';
import { api, tokenStore } from './api';

interface AuthCtx { user: User | null; role: Role; loading: boolean; login: (email: string, pw: string) => Promise<User>; logout: () => void }
const Ctx = createContext<AuthCtx>({ user: null, role: 'public', loading: true, login: async () => { throw new Error('no provider'); }, logout: () => {} });

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!tokenStore.get()) { setLoading(false); return; }
    api<User>('/auth/me').then(setUser).catch(() => tokenStore.clear()).finally(() => setLoading(false));
  }, []);
  const login = useCallback(async (email: string, password: string) => {
    const r = await api<{ access_token: string; user: User }>('/auth/login', { body: { email, password } });
    tokenStore.set(r.access_token); setUser(r.user); return r.user;
  }, []);
  const logout = useCallback(() => { tokenStore.clear(); setUser(null); }, []);
  const value = useMemo(() => ({ user, role: (user?.role ?? 'public') as Role, loading, login, logout }), [user, loading, login, logout]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
export const useAuth = () => useContext(Ctx);
export const can = {
  workspace: (r: Role) => r !== 'public', run: (r: Role) => r !== 'public',
  export: (r: Role) => ['analyst', 'expert', 'admin'].includes(r), review: (r: Role) => ['expert', 'admin'].includes(r), admin: (r: Role) => r === 'admin',
};
