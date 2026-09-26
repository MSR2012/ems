import { useEffect, useState, type FormEvent } from 'react';
import { useChangePassword, useMe, useUpdateProfile } from '@/features/auth/api';
import { FormError, TextField, fieldErrors } from '@/shared/ui/Form';
import { Alert, LoadingState, PageHeader } from '@/shared/ui/feedback';
import { formatDateTime } from '@/shared/lib/format';
import { BulkAnalyzeButton } from '@/features/email-analysis/BulkAnalyzeButton';

function ProfileCard() {
  const { data: me } = useMe();
  const update = useUpdateProfile();
  const [name, setName] = useState(me?.name ?? '');
  useEffect(() => setName(me?.name ?? ''), [me?.name]);
  if (!me) return null;
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    update.mutate({ name });
  };
  return (
    <section className="card p-5 sm:p-6">
      <h2 className="text-base font-semibold">Profile</h2>
      <p className="mt-1 text-sm text-slate-500">Member since {formatDateTime(me.created_at)}</p>
      <form className="mt-5 grid gap-4 sm:max-w-md" onSubmit={onSubmit} noValidate>
        {update.isSuccess && <Alert tone="success">Profile saved.</Alert>}
        <FormError error={update.error} fields={['name']} />
        <TextField label="Email" name="email" value={me.email} disabled readOnly />
        <TextField label="Name" name="name" value={name} onChange={(e) => setName(e.target.value)}
          errors={fieldErrors(update.error, 'name')} maxLength={150} />
        <div><button className="btn-primary" type="submit" disabled={update.isPending}>{update.isPending ? 'Saving…' : 'Save profile'}</button></div>
      </form>
    </section>
  );
}

function PasswordCard() {
  const change = useChangePassword();
  const [form, setForm] = useState({ current_password: '', new_password: '' });
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    change.mutate(form, { onSuccess: () => setForm({ current_password: '', new_password: '' }) });
  };
  return (
    <section className="card p-5 sm:p-6">
      <h2 className="text-base font-semibold">Password</h2>
      <form className="mt-5 grid gap-4 sm:max-w-md" onSubmit={onSubmit} noValidate>
        {change.isSuccess && <Alert tone="success">Password updated.</Alert>}
        <FormError error={change.error} fields={['current_password', 'new_password']} />
        <TextField label="Current password" name="current_password" type="password" autoComplete="current-password"
          value={form.current_password} onChange={(e) => setForm({ ...form, current_password: e.target.value })}
          errors={fieldErrors(change.error, 'current_password')} />
        <TextField label="New password" name="new_password" type="password" autoComplete="new-password"
          value={form.new_password} onChange={(e) => setForm({ ...form, new_password: e.target.value })}
          errors={fieldErrors(change.error, 'new_password')} />
        <div><button className="btn-secondary" type="submit" disabled={change.isPending}>{change.isPending ? 'Updating…' : 'Change password'}</button></div>
      </form>
    </section>
  );
}

function AiCard() {
  const { data: me } = useMe();
  if (!me) return null;
  const s = me.settings;
  return (
    <section className="card p-5 sm:p-6">
      <h2 className="text-base font-semibold">AI analysis &amp; privacy</h2>
      <div className="mt-3 space-y-3 text-sm text-slate-600">
        <p>
          Email content (sender, subject and body text — never attachments) is processed by <strong>{s.ai_provider_name}</strong> to
          estimate priority, category, spam likelihood and reply urgency. These are AI suggestions, not facts, and the app never
          deletes, archives, replies to or otherwise changes your Gmail messages.
        </p>
        <dl className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg bg-slate-50 p-3">
            <dt className="text-xs uppercase tracking-wide text-slate-500">Potential spam threshold</dt>
            <dd className="mt-1 text-lg font-semibold text-slate-800">≥ {s.spam_threshold_percent}%</dd>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <dt className="text-xs uppercase tracking-wide text-slate-500">High reply-urgency threshold</dt>
            <dd className="mt-1 text-lg font-semibold text-slate-800">≥ {s.urgency_threshold_percent}%</dd>
          </div>
        </dl>
        <div className="flex flex-col gap-2 border-t border-slate-100 pt-3 sm:flex-row sm:items-start sm:justify-between">
          <p className="text-sm">Run the analysis for your whole inbox with the current model and prompt version.</p>
          <BulkAnalyzeButton />
        </div>
        <p className="text-xs text-slate-500">Thresholds are configured by the operator (<code>SPAM_THRESHOLD_PERCENT</code>, <code>URGENCY_THRESHOLD_PERCENT</code>).</p>
        {s.demo_mode && <Alert tone="info">Demo mode is on: Gmail and AI use built-in simulators, no external credentials needed.</Alert>}
      </div>
    </section>
  );
}

export default function SettingsPage() {
  const { data: me, isLoading } = useMe();
  if (isLoading || !me) return <LoadingState />;
  return (
    <>
      <PageHeader title="Settings" description="Your profile, password and how AI analysis works." />
      <div className="grid gap-6">
        <ProfileCard />
        <PasswordCard />
        <AiCard />
      </div>
    </>
  );
}
