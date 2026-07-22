import { useNavigate } from 'react-router-dom';

export function AuthCallbackPage() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen items-center justify-center bg-warm-bg px-4">
      <div className="w-full max-w-md rounded-xl border border-[var(--color-border)] bg-warm-card p-6 text-center shadow-card-md">
        <h1 className="text-lg font-bold text-[var(--color-brand-navy)]">Outlook authentication</h1>
        <p className="mt-2 text-sm text-gray-500">
          Outlook now connects in a popup. This page does not start sign-in or redirect automatically.
        </p>
        <button
          type="button"
          onClick={() => navigate('/settings', { replace: true })}
          className="mt-5 rounded-btn bg-[var(--color-text-primary)] px-4 py-2 text-sm font-semibold text-warm-card"
        >
          Return to Settings
        </button>
      </div>
    </div>
  );
}
