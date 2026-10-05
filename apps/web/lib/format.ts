export const DOC_TYPE_LABEL: Record<string, string> = {
  policy_report: 'Policy report', research_paper: 'Research paper', legal_text: 'Legal text', case_study: 'Case study',
  dataset_description: 'Dataset description', brief: 'Policy brief',
};
export const STATE_NAME: Record<string, string> = { KA: 'Karnataka', MH: 'Maharashtra', TN: 'Tamil Nadu', OD: 'Odisha' };
export const fmtNum = (n: number | null | undefined, d = 1) => (n == null || Number.isNaN(n) ? '—' : n.toLocaleString('en-IN', { maximumFractionDigits: d }));
export const fmtPct = (n: number | null | undefined) => (n == null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(1)}%`);
export const fmtDate = (s: string | null) => (s ? new Date(s).toLocaleDateString('en-IN', { year: 'numeric', month: 'short' }) : 'n.d.');
