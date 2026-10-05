const RAMP_POS = ['#e3f1ec', '#b5dccf', '#6fbba5', '#2f8f78', '#0b5d4b'];
const RAMP_NEG = ['#fbf0d9', '#f3d79a', '#e2ac55', '#c4762a', '#8f3b1b'];

export function colorFor(value: number | null | undefined, legend: [number, number], higherIsBetter: boolean): string {
  if (value == null) return '#d5dade';
  const t = Math.max(0, Math.min(0.9999, (value - legend[0]) / (legend[1] - legend[0] || 1)));
  return (higherIsBetter ? RAMP_POS : RAMP_NEG)[Math.floor(t * 5)];
}
export const legendSteps = (legend: [number, number], hib: boolean) =>
  (hib ? RAMP_POS : RAMP_NEG).map((c, i) => ({ color: c, from: legend[0] + ((legend[1] - legend[0]) * i) / 5, to: legend[0] + ((legend[1] - legend[0]) * (i + 1)) / 5 }));
