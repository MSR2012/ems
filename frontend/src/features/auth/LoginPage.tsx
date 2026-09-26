import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { FormError, TextField, fieldErrors } from '@/shared/ui/Form';
import { Alert } from '@/shared/ui/feedback';
import { useLogin } from './api';
import { AuthLayout } from './AuthLayout';
import { safeNext } from './guards';

export default function LoginPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const login = useLogin();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    login.mutate({ email, password }, { onSuccess: () => navigate(safeNext(params.get('next')), { replace: true }) });
  };

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Welcome back. Sign in to see what needs your attention."
      footer={<>New here? <Link className="font-medium text-indigo-600 hover:underline" to="/register">Create an account</Link></>}
    >
      {params.get('reset') === '1' && <div className="mb-4"><Alert tone="success">Password updated — sign in with your new password.</Alert></div>}
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        <FormError error={login.error} fields={['email', 'password']} />
        <TextField label="Email" name="email" type="email" autoComplete="email" required value={email}
          onChange={(e) => setEmail(e.target.value)} errors={fieldErrors(login.error, 'email')} />
        <TextField label="Password" name="password" type="password" autoComplete="current-password" required value={password}
          onChange={(e) => setPassword(e.target.value)} errors={fieldErrors(login.error, 'password')} />
        <div className="flex justify-end">
          <Link to="/password-reset" className="text-sm font-medium text-indigo-600 hover:underline">Forgot password?</Link>
        </div>
        <button type="submit" className="btn-primary w-full" disabled={login.isPending}>
          {login.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthLayout>
  );
}
