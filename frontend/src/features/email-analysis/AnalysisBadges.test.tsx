import { render, screen } from '@testing-library/react';
import { analysis } from '@/test/utils';
import { AnalysisIndicators, hasAnalysisInFlight } from './AnalysisBadges';

describe('AnalysisIndicators', () => {
  it('shows priority, category, urgency % and spam % for a completed analysis', () => {
    render(<AnalysisIndicators analysis={analysis()} />);
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('Customer')).toBeInTheDocument();
    expect(screen.getByText(/91%/)).toBeInTheDocument();
    expect(screen.getByText(/Spam 4%/)).toBeInTheDocument();
    expect(screen.getByText('High')).toHaveAttribute('title', expect.stringContaining('AI suggestion'));
  });

  it('highlights potential spam above the threshold', () => {
    render(<AnalysisIndicators analysis={analysis({ spam_likelihood: 92, is_potential_spam: true })} />);
    expect(screen.getByText(/Spam\? 92%/)).toBeInTheDocument();
  });

  it('shows Analyzing when pending or missing, and failure state', () => {
    const { rerender } = render(<AnalysisIndicators analysis={null} />);
    expect(screen.getByText('Analyzing')).toBeInTheDocument();
    rerender(<AnalysisIndicators analysis={analysis({ status: 'PENDING', priority: null })} />);
    expect(screen.getByText('Analyzing')).toBeInTheDocument();
    rerender(<AnalysisIndicators analysis={analysis({ status: 'FAILED', error: 'bad output' })} />);
    expect(screen.getByText('Analysis failed')).toBeInTheDocument();
  });

  it('detects in-flight (re-)analysis for polling', () => {
    expect(hasAnalysisInFlight(analysis())).toBe(false);
    expect(hasAnalysisInFlight(analysis({ latest_status: 'PENDING' }))).toBe(true);
    expect(hasAnalysisInFlight(null)).toBe(true);
  });
});
