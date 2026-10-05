import { describe, expect, it } from 'vitest';
import { colorFor, legendSteps } from '@/lib/mapColors';
import { fmtNum, fmtPct } from '@/lib/format';
import { can } from '@/lib/auth';

describe('map colour scale', () => {
  it('clamps, handles missing values, and respects polarity', () => {
    expect(colorFor(null, [0, 100], true)).toBe('#d5dade');
    expect(colorFor(-50, [0, 100], true)).toBe(colorFor(0, [0, 100], true));
    expect(colorFor(500, [0, 100], true)).toBe(colorFor(100, [0, 100], true));
    expect(colorFor(90, [0, 100], true)).not.toBe(colorFor(90, [0, 100], false));
    expect(legendSteps([0, 100], true)).toHaveLength(5);
  });
});
describe('formatters & role helpers', () => {
  it('formats numbers', () => { expect(fmtNum(null)).toBe('—'); expect(fmtPct(-16.2)).toBe('-16.2%'); expect(fmtPct(4)).toBe('+4.0%'); });
  it('mirrors server capability matrix (UI hints only; server enforces)', () => {
    expect(can.workspace('public')).toBe(false); expect(can.export('researcher')).toBe(false); expect(can.export('analyst')).toBe(true);
    expect(can.review('expert')).toBe(true); expect(can.admin('expert')).toBe(false);
  });
});
