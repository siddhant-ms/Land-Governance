import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AskResponse, Source } from '@sih/types';
import { AnswerView, CitationChip, HighlightedPassage, SourcePanel } from '@/components/citations';
import { ErrorState } from '@/components/ui';
import { ApiError } from '@/lib/api';

const PASSAGE = 'Intro sentence here. Digitization of land records can reduce administrative friction. Closing sentence follows.';
const start = PASSAGE.indexOf('Digitization');
const source: Source = {
  citation_id: 'citation_1', number: 1, label: 'E1', chunk_id: 'c1', document_id: 'd1', title: 'Land Record Report (DEMO)', organization: 'Demo Institute (fictional)',
  publication_date: '2024-03-15', year: 2024, document_type: 'policy_report', authority_level: 'demo', state_code: null, geography: 'India', source_url: '',
  access_level: 'public', is_demo: true, topics: [], page: 3, section: 'Effects on disputes', passage: PASSAGE,
  highlights: [[start, start + 'Digitization of land records can reduce administrative friction.'.length]], relevance: 0.56, rank: 1,
  explain: { bm25: 3, dense_cosine: 0.4, rank_lexical: 1, rank_dense: 2, rrf: 0.0325, query_coverage: 0.75, relevance: 0.56, boosts: {}, final_score: 0.9, matched_terms: [] },
};
const ask = (over: Partial<AskResponse> = {}): AskResponse => ({
  question: 'q', answer: '', summary: '', claims: [{ text: 'Digitization of land records can reduce administrative friction.', citations: ['citation_1'], numbers: [1], kind: 'source_extract', support: 1, strength: 'strong' }],
  sources: [source], limitations: ['DEMO CORPUS: illustrative.'], evidence_gap: false, evidence_gap_message: null, evidence_strength: 'moderate', ai_status: 'ok', ai_message: null,
  retrieved: [], query_analysis: {}, suggested_followups: [], pipeline: { provider: 'extractive', timings_ms: { total: 5 }, validation: { proposed: 1, kept: 1, removed: [], invalid_citation_ids: [], downgraded: 0 } }, ...over,
});

describe('CitationChip', () => {
  it('is an accessible button that reports its number', () => {
    const fn = vi.fn(); render(<CitationChip n={2} onClick={fn} />);
    fireEvent.click(screen.getByRole('button', { name: 'Open source 2' })); expect(fn).toHaveBeenCalledWith(2);
  });
});

describe('HighlightedPassage', () => {
  it('highlights exactly the supporting span', () => {
    render(<HighlightedPassage text={PASSAGE} ranges={source.highlights} />);
    expect(screen.getByTestId('supporting-span')).toHaveTextContent('Digitization of land records can reduce administrative friction.');
  });
  it('ignores invalid and merges overlapping ranges', () => {
    render(<HighlightedPassage text="abcdefghij" ranges={[[2, 5], [4, 8], [-1, 3], [9, 99]]} />);
    const marks = screen.getAllByTestId('supporting-span'); expect(marks).toHaveLength(1); expect(marks[0]).toHaveTextContent('cdefgh');
  });
  it('renders hostile text as text, not HTML', () => {
    const { container } = render(<HighlightedPassage text={'<img src=x onerror=alert(1)> payload'} ranges={[]} />);
    expect(container.querySelector('img')).toBeNull();
  });
});

describe('SourcePanel', () => {
  it('shows every citation field required by the brief', () => {
    render(<SourcePanel source={source} onClose={() => {}} />);
    const d = within(screen.getByRole('dialog'));
    for (const t of ['Demo Institute (fictional)', 'Land Record Report (DEMO)', 'Effects on disputes', 'Supporting passage', 'Retrieval relevance', 'No public URL — demo document', 'DEMO SOURCE']) expect(d.getByText(t)).toBeInTheDocument();
    expect(d.getByText('3')).toBeInTheDocument(); expect(d.getByTestId('supporting-span')).toBeInTheDocument();
    expect(d.getByRole('link', { name: /Open in document/ })).toHaveAttribute('href', '/research/document/d1?chunk=c1');
  });
  it('closes on Escape and renders nothing without a source', () => {
    const fn = vi.fn(); const { container, rerender } = render(<SourcePanel source={source} onClose={fn} />);
    fireEvent.keyDown(window, { key: 'Escape' }); expect(fn).toHaveBeenCalled();
    rerender(<SourcePanel source={null} onClose={fn} />); expect(container).toBeEmptyDOMElement();
  });
});

describe('AnswerView', () => {
  it('renders claims with citation chips that open the matching source', () => {
    const open = vi.fn(); render(<AnswerView ask={ask()} activeN={null} onOpen={open} />);
    expect(screen.getAllByTestId('claim')).toHaveLength(1); expect(screen.getByText(/verbatim from source/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Open source 1' })); expect(open).toHaveBeenCalledWith(1);
    expect(screen.getByText(/Uncertainty & limitations/)).toBeInTheDocument(); expect(screen.getByText(/DEMO CORPUS/)).toBeInTheDocument();
  });
  it('shows the evidence-gap state instead of an answer', () => {
    render(<AnswerView ask={ask({ evidence_gap: true, claims: [], sources: [], evidence_gap_message: 'The available corpus does not contain enough evidence to answer this confidently.', evidence_strength: 'none' })} activeN={null} onOpen={() => {}} />);
    expect(screen.getByTestId('evidence-gap')).toHaveTextContent('does not contain enough evidence'); expect(screen.queryByTestId('claim')).toBeNull();
  });
  it('shows the AI-failure message', () => {
    render(<AnswerView ask={ask({ ai_status: 'failed', ai_message: 'The research assistant could not complete the synthesis. Your retrieved evidence is still available below.' })} activeN={null} onOpen={() => {}} />);
    expect(screen.getByRole('alert')).toHaveTextContent('retrieved evidence is still available');
  });
  it('flags partially supported claims', () => {
    const a = ask(); a.claims[0].strength = 'partial'; render(<AnswerView ask={a} activeN={null} onOpen={() => {}} />);
    expect(screen.getByText(/partial support/)).toBeInTheDocument();
  });
});

describe('ErrorState', () => {
  it('shows the restricted-document state', () => {
    render(<ErrorState error={new ApiError(403, 'RESTRICTED_DOCUMENT', 'This document exists in the repository but is restricted to authorized users.')} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Restricted'); expect(screen.getByRole('alert')).toHaveTextContent('restricted to authorized users');
  });
  it('prompts sign-in on 401', () => {
    render(<ErrorState error={new ApiError(401, 'AUTH_REQUIRED', 'Sign in to use this feature.')} />); expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument();
  });
});
