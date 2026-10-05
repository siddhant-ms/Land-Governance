import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/lib/auth';
import Shell from '@/components/Shell';

export const metadata: Metadata = {
  title: 'Land Governance Evidence Platform — SIH26019',
  description: 'Evidence retrieval with inspectable citations, spatial context and transparent policy scenarios.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (<html lang="en"><body><AuthProvider><Shell>{children}</Shell></AuthProvider></body></html>);
}
