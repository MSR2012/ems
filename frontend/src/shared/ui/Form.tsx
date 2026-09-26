import type { InputHTMLAttributes } from 'react';
import { ApiError } from '@/shared/api/client';
import { Alert } from './feedback';

export function TextField({ label, name, errors, hint, ...rest }: InputHTMLAttributes<HTMLInputElement> & {
  label: string; name: string; errors?: string[]; hint?: string;
}) {
  const id = `f-${name}`;
  const describedBy = errors?.length ? `${id}-err` : hint ? `${id}-hint` : undefined;
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <input
        id={id}
        name={name}
        className={`input ${errors?.length ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-500' : ''}`}
        aria-invalid={errors?.length ? true : undefined}
        aria-describedby={describedBy}
        {...rest}
      />
      {hint && !errors?.length && <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">{hint}</p>}
      {errors?.map((e) => (
        <p key={e} id={`${id}-err`} className="mt-1 text-xs text-rose-600">{e}</p>
      ))}
    </div>
  );
}

/** Non-field error banner for a failed mutation (field errors are shown inline). */
export function FormError({ error, fields = [] }: { error: unknown; fields?: string[] }) {
  if (!error) return null;
  if (error instanceof ApiError) {
    const fe = error.fieldErrors;
    const hasOnlyFieldErrors = Object.keys(fe).length > 0 && Object.keys(fe).every((k) => fields.includes(k));
    if (hasOnlyFieldErrors) return null;
    const other = Object.entries(fe).filter(([k]) => !fields.includes(k)).flatMap(([, v]) => v);
    const msg = ApiError.messageFrom(error.data) ?? other[0] ?? (error.status === 429 ? 'Too many attempts. Please wait a minute and try again.' : error.message);
    return <Alert tone="error">{msg}</Alert>;
  }
  return <Alert tone="error">Network error — please check your connection and try again.</Alert>;
}

export function fieldErrors(error: unknown, field: string): string[] | undefined {
  return error instanceof ApiError ? error.fieldErrors[field] : undefined;
}
