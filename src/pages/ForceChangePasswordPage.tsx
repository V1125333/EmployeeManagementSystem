import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Loader2, Lock, ShieldCheck } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/utils/cn';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export function ForceChangePasswordPage() {
  const navigate = useNavigate();
  const { user, isAuthenticated, updateUser, logout } = useAuth();
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!user?.forcePasswordChange) {
    return <Navigate to="/" replace />;
  }

  const inputClass = cn(
    'w-full rounded-xl border border-[var(--color-border)] bg-warm-bg py-3 pl-10 pr-11 text-[14px] font-medium text-[var(--color-brand-navy)]',
    'outline-none transition-all placeholder:text-gray-400 focus:border-olive/40 focus:ring-2 focus:ring-olive/10',
  );

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/auth/force-change-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-user-id': user.id || '',
          'x-user-email': user.email,
        },
        body: JSON.stringify({
          new_password: newPassword,
          confirm_password: confirmPassword,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        setError(data.detail || data.message || 'Could not change password.');
        return;
      }
      updateUser({ forcePasswordChange: false });
      navigate('/', { replace: true });
    } catch {
      setError('Cannot connect to server. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-warm-bg px-6 py-12 font-sans">
      <div className="w-full max-w-[460px] rounded-2xl border border-[var(--color-border)] bg-warm-card p-8 shadow-card-md">
        <div className="mb-7 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-olive/10">
            <ShieldCheck size={23} className="text-olive" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--color-brand-navy)]">Create new password</h1>
          <p className="mt-2 text-sm leading-6 text-gray-500">
            Temporary password verified. Create a new password before continuing.
          </p>
        </div>

        {error && (
          <div className="mb-5 rounded-xl border border-status-error/15 bg-status-error/5 px-4 py-3 text-[13px] font-medium text-status-error">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {[
            ['New password', newPassword, setNewPassword],
            ['Confirm new password', confirmPassword, setConfirmPassword],
          ].map(([label, value, setter]) => (
            <label key={label as string} className="block">
              <span className="mb-2 block text-[13px] font-semibold text-[var(--color-brand-navy)]">{label as string}</span>
              <span className="relative block">
                <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={value as string}
                  onChange={(event) => (setter as (value: string) => void)(event.target.value)}
                  className={inputClass}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((open) => !open)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 transition-colors hover:text-gray-600"
                  aria-label={showPassword ? 'Hide passwords' : 'Show passwords'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </span>
            </label>
          ))}

          <div className="rounded-xl bg-warm-bg px-4 py-3 text-[12px] leading-5 text-gray-500">
            Use at least 8 characters with uppercase, lowercase, number, and special character.
          </div>

          <button
            type="submit"
            disabled={loading}
            className={cn(
              'flex w-full items-center justify-center gap-2 rounded-xl py-3.5 text-[15px] font-semibold text-white transition-all',
              loading ? 'cursor-not-allowed bg-olive/60' : 'bg-olive shadow-sm hover:bg-olive-dark active:scale-[0.99]',
            )}
          >
            {loading && <Loader2 size={16} className="animate-spin" />}
            {loading ? 'Changing password...' : 'Change Password'}
          </button>

          <button type="button" onClick={logout} className="w-full text-center text-[13px] font-semibold text-gray-500 hover:text-olive">
            Sign out instead
          </button>
        </form>
      </div>
    </div>
  );
}
