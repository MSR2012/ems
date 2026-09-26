import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { FormError, TextField, fieldErrors } from '@/shared/ui/Form';
import { Alert } from '@/shared/ui/feedback';
import { useConfirmPasswordReset } from './api';
import { AuthLayout } from './AuthLayout';

export default function PasswordResetConfirmPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const confirm = useConfirmPasswordReset();
  const [password, setPassword] = useState('');
  const [again, setAgain] = useState('');
  const [mismatch, setMismatch] = useState(false);
  const uid = params.get('uid') ?? '';
  const token = params.get('token') ?? '';

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (password !== again) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    confirm.mutate({ uid, token, new_password: password }, {
      onSuccess: () => navigate('/login?reset=1', { replace: true }),
    });
  };

  const tokenErr = fieldErrors(confirm.error, 'token');
  return (
    <AuthLayout title="Choose a new password"
      footer={<Link className="font-medium text-indigo-600 hover:underline" to="/login">Back to sign in</Link>}>
      {!uid || !token ? (
        <Alert tone="error">This reset link is incomplete. Request a new one from the <Link className="underline" to="/password-reset">reset page</Link>.</Alert>
      ) : (
        <form className="space-y-4" onSubmit={onSubmit} noValidate>
          {tokenErr && <Alert tone="error">{tokenErr[0]} <Link className="underline" to="/password-reset">Request a new link</Link>.</Alert>}
          <FormError error={confirm.error} fields={['new_password', 'token']} />
          <TextField label="New password" name="new_password" type="password" autoComplete="new-password" required
            value={password} onChange={(e) => setPassword(e.target.value)} errors={fieldErrors(confirm.error, 'new_password')} />
          <TextField label="Confirm new password" name="confirm_password" type="password" autoComplete="new-password" required
            value={again} onChange={(e) => setAgain(e.target.value)} errors={mismatch ? ['Passwords do not match.'] : undefined} />
          <button type="submit" className="btn-primary w-full" disabled={confirm.isPending}>
            {confirm.isPending ? 'Saving…' : 'Set new password'}
          </button>
        </form>
      )}
    </AuthLayout>
  );
}
