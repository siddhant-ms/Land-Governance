'use client';
import { Search } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Card, PageHeader } from '@/components/ui';

const EXAMPLES = [
  'What evidence exists on land-record digitization and land-dispute outcomes in India?',
  'How does implementation capacity affect the benefits of digitization?',
  'What do studies say about boundary disputes and cadastral mapping?',
  'How does climate vulnerability affect tenure security in coastal Odisha?',
];

export default function Research() {
  const router = useRouter();
  const [q, setQ] = useState('');
  const go = (t: string) => t.trim().length >= 5 && router.push(`/research/results?q=${encodeURIComponent(t.trim())}`);
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Evidence Repository" title="Research assistant" sub="Hybrid search (BM25 + dense retrieval, fused with Reciprocal Rank Fusion) over the curated corpus. Every statement in an answer links to the exact passage it came from." />
      <form onSubmit={(e) => { e.preventDefault(); go(q); }} className="flex gap-2">
        <input aria-label="Research question" autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask a land-governance policy question…" className="min-w-0 flex-1 rounded-md border border-ink-200 bg-white px-4 py-3 text-base shadow-card" />
        <button className="inline-flex items-center gap-2 rounded-md bg-brand px-5 py-3 font-medium text-white hover:bg-brand-700"><Search className="h-4 w-4" />Search</button></form>
      <Card className="mt-6 p-5"><p className="label mb-3">Example questions</p>
        <ul className="space-y-2">{EXAMPLES.map((e) => <li key={e}><button className="text-left text-sm text-brand hover:underline" onClick={() => go(e)}>{e}</button></li>)}</ul></Card>
    </div>);
}
