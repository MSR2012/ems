import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { FormError, TextField, fieldErrors } from '@/shared/ui/Form';
import { Alert } from '@/shared/ui/feedback';
import { useRequestPasswordReset } from './api';
import { AuthLayout } from './AuthLayout';

export default function PasswordResetPage() {
  const reset = useRequestPasswordReset();
  const [email, setEmail] = useState('');
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    reset.mutate({ email });
  };
  return (
    <AuthLayout
      title="Reset your password"
      subtitle="Enter your account email and we'll send you a reset link."
      footer={<Link className="font-medium text-indigo-600 hover:underline" to="/login">Back to sign in</Link>}
    >
      {reset.isSuccess ? (
        <Alert tone="success" title="Check your email">
          {reset.data.detail} In development the email is printed to the API server log (<code>make logs</code>).
        </Alert>
      ) : (
        <form className="space-y-4" onSubmit={onSubmit} noValidate>
          <FormError error={reset.error} fields={['email']} />
          <TextField label="Email" name="email" type="email" autoComplete="email" required value={email}
            onChange={(e) => setEmail(e.target.value)} errors={fieldErrors(reset.error, 'email')} />
          <button type="submit" className="btn-primary w-full" disabled={reset.isPending}>
            {reset.isPending ? 'Sending…' : 'Send reset link'}
          </button>
        </form>
      )}
    </AuthLayout>
  );
}
