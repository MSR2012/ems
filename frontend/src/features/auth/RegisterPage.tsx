import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FormError, TextField, fieldErrors } from '@/shared/ui/Form';
import { useRegister } from './api';
import { AuthLayout } from './AuthLayout';

export default function RegisterPage() {
  const navigate = useNavigate();
  const register = useRegister();
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    register.mutate(form, { onSuccess: () => navigate('/', { replace: true }) });
  };

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Connect Gmail and let AI surface what needs attention."
      footer={<>Already have an account? <Link className="font-medium text-indigo-600 hover:underline" to="/login">Sign in</Link></>}
    >
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        <FormError error={register.error} fields={['name', 'email', 'password']} />
        <TextField label="Name" name="name" autoComplete="name" value={form.name} onChange={set('name')}
          errors={fieldErrors(register.error, 'name')} />
        <TextField label="Email" name="email" type="email" autoComplete="email" required value={form.email}
          onChange={set('email')} errors={fieldErrors(register.error, 'email')} />
        <TextField label="Password" name="password" type="password" autoComplete="new-password" required
          value={form.password} onChange={set('password')} errors={fieldErrors(register.error, 'password')}
          hint="At least 8 characters; not too common or entirely numeric." />
        <button type="submit" className="btn-primary w-full" disabled={register.isPending}>
          {register.isPending ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthLayout>
  );
}
