import type { ReactNode } from 'react';
import { IconMail } from '@/shared/ui/icons';

export function AuthLayout({ title, subtitle, children, footer }: {
  title: string; subtitle?: ReactNode; children: ReactNode; footer?: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-indigo-50 to-slate-50 px-4 py-10">
      <div className="mb-6 flex items-center gap-2">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow">
          <IconMail className="h-5 w-5" />
        </span>
        <span className="text-xl font-semibold tracking-tight">Inbox AI</span>
      </div>
      <div className="card w-full max-w-md p-6 sm:p-8">
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
        <div className="mt-6">{children}</div>
      </div>
      {footer && <div className="mt-6 text-sm text-slate-600">{footer}</div>}
    </div>
  );
}
