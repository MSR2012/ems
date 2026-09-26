import { useCallback, useMemo, useRef, useState } from 'react';
import DOMPurify from 'dompurify';

/**
 * Renders untrusted email HTML safely (§20.3):
 * - HTML was already sanitized server-side (nh3); DOMPurify runs again here as defense in depth.
 * - Rendered in a sandboxed `<iframe srcdoc>` WITHOUT `allow-scripts`, so no script can run.
 *   (`allow-same-origin` without scripts is safe and lets us size the frame to its content.)
 * - A restrictive CSP inside the frame blocks every network fetch except inline data: images,
 *   so remote images / tracking pixels never load.
 */
const CSP = "default-src 'none'; img-src data: cid:; style-src 'unsafe-inline'; font-src data:";

let hooked = false;
function purify(html: string): string {
  if (!hooked) {
    DOMPurify.addHook('afterSanitizeAttributes', (node) => {
      if (node.tagName === 'IMG') {
        const src = node.getAttribute('src') ?? '';
        if (!/^(data:image\/|cid:)/i.test(src)) node.removeAttribute('src');
        node.removeAttribute('srcset');
      }
      if (node.tagName === 'A') {
        node.setAttribute('target', '_blank');
        node.setAttribute('rel', 'noopener noreferrer nofollow');
      }
      const style = node.getAttribute?.('style');
      if (style && /url\s*\(|expression\s*\(|@import/i.test(style)) node.removeAttribute('style');
    });
    hooked = true;
  }
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['style', 'script', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'link', 'meta', 'base', 'svg', 'math'],
    FORBID_ATTR: ['srcset', 'background', 'formaction'],
  });
}

export function SafeEmailBody({ html, text }: { html: string; text: string }) {
  const ref = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(200);
  const srcDoc = useMemo(() => {
    if (!html.trim()) return '';
    return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${CSP}"><base target="_blank"><style>body{margin:0;padding:4px 2px;font:14px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;color:#0f172a;word-wrap:break-word;overflow-wrap:anywhere}img{max-width:100%;height:auto}table{max-width:100%}a{color:#4f46e5}pre{white-space:pre-wrap}</style></head><body>${purify(html)}</body></html>`;
  }, [html]);

  const resize = useCallback(() => {
    const doc = ref.current?.contentDocument;
    if (doc?.body) setHeight(Math.min(Math.max(doc.documentElement.scrollHeight, 80), 4000));
  }, []);

  if (!srcDoc) {
    return text.trim() ? (
      <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-slate-800">{text}</pre>
    ) : (
      <p className="text-sm italic text-slate-400">This message has no text content.</p>
    );
  }
  return (
    <iframe
      ref={ref}
      title="Email content"
      sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
      referrerPolicy="no-referrer"
      srcDoc={srcDoc}
      onLoad={resize}
      className="w-full border-0"
      style={{ height }}
    />
  );
}
