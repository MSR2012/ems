import { act, render, screen } from '@testing-library/react';
import { SafeEmailBody } from './SafeEmailBody';

describe('SafeEmailBody', () => {
  it('renders HTML in a sandboxed iframe without allow-scripts and strips dangerous content', async () => {
    const html = `<p onclick="alert(1)">Hi</p><script>alert('x')</script><img src="https://tracker.example.com/p.gif"><a href="javascript:alert(1)">x</a>`;
    render(<SafeEmailBody html={html} text="" />);
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); }); // let the iframe load/resize
    const frame = screen.getByTitle('Email content') as HTMLIFrameElement;
    expect(frame.getAttribute('sandbox')).not.toContain('allow-scripts');
    const doc = frame.getAttribute('srcdoc') ?? '';
    expect(doc).toContain('Content-Security-Policy');
    expect(doc).toContain("default-src 'none'");
    expect(doc).toContain('<p>Hi</p>');
    expect(doc).not.toMatch(/<script|onclick|tracker\.example\.com|javascript:/i);
  });

  it('falls back to escaped plain text when there is no HTML', () => {
    render(<SafeEmailBody html="" text={'<b>not bold</b>\nline two'} />);
    expect(screen.getByText(/<b>not bold<\/b>/)).toBeInTheDocument();
    expect(screen.queryByTitle('Email content')).not.toBeInTheDocument();
  });
});
