import { useNavigate } from 'react-router-dom';
import { IconLogout } from '@/shared/ui/icons';
import { useLogout, useMe } from './api';

export function UserMenu() {
  const { data: me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  if (!me) return null;
  const initials = (me.name || me.email).split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join('');
  return (
    <div className="mt-4 border-t border-slate-200 pt-4">
      <div className="flex items-center gap-3 px-1">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-sm font-semibold text-slate-700">{initials}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-800">{me.name || 'Account'}</p>
          <p className="truncate text-xs text-slate-500">{me.email}</p>
        </div>
      </div>
      <button
        type="button"
        className="btn-ghost mt-3 w-full justify-start"
        disabled={logout.isPending}
        onClick={() => logout.mutate(undefined, { onSettled: () => navigate('/login', { replace: true }) })}
      >
        <IconLogout className="h-4 w-4" /> Sign out
      </button>
    </div>
  );
}
