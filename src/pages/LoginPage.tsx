import { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import {
  Mail, Lock, Eye, EyeOff, ShieldCheck, Loader2,
  KeyRound, QrCode, Smartphone, ArrowLeft, CheckCircle,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { useAuth } from '@/hooks/useAuth';

const API_BASE = 'http://localhost:8000/api/v1';

type Step =
  | 'email'           // Enter email
  | 'setup_code'      // First-time: enter setup code
  | 'create_password' // First-time: create password
  | 'scan_qr'         // First-time: scan QR with authenticator
  | 'confirm_totp'    // First-time: enter 6-digit code to confirm
  | 'setup_complete'  // First-time: success screen
  | 'login_password'  // Returning: enter password
  | 'login_totp';     // Returning: enter authenticator code

export function LoginPage() {
  const navigate = useNavigate();
  const { isAuthenticated, loginWithApi, loginAdmin, setUserFromApi } = useAuth();

  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [setupCode, setSetupCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // QR code data from API
  const [qrBase64, setQrBase64] = useState('');
  const [totpSecret, setTotpSecret] = useState('');

  // Track if first-time user
  const [isFirstLogin, setIsFirstLogin] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const resetForm = () => {
    setSetupCode('');
    setPassword('');
    setConfirmPassword('');
    setTotpCode('');
    setShowPassword(false);
    setError('');
    setQrBase64('');
    setTotpSecret('');
  };

  const goBack = () => {
    setError('');
    if (step === 'setup_code' || step === 'login_password') {
      resetForm();
      setStep('email');
    } else if (step === 'create_password') setStep('setup_code');
    else if (step === 'scan_qr') setStep('create_password');
    else if (step === 'confirm_totp') setStep('scan_qr');
    else if (step === 'login_totp') setStep('login_password');
  };

  // ─── Step 1: Check Email ───
  const handleCheckEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) { setError('Please enter your email'); return; }
    setError('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/auth/check-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();

      if (!data.exists) {
        setError('Account not found. Contact your administrator.');
      } else if (data.is_first_login) {
        setIsFirstLogin(true);
        setStep('setup_code');
      } else {
        setIsFirstLogin(false);
        setStep('login_password');
      }
    } catch {
      // Backend not available — try admin fallback
      if (email === 'superadmin@reknew.ai') {
        setIsFirstLogin(false);
        setStep('login_password');
      } else {
        setError('Cannot connect to server. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  // ─── Step 2: Verify Setup Code ───
  const handleVerifySetupCode = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!setupCode.trim()) { setError('Please enter the setup code'); return; }
    setError('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/auth/verify-setup-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, setup_code: setupCode }),
      });
      const data = await res.json();

      if (data.success) {
        setStep('create_password');
      } else {
        setError('Invalid setup code. Please check with your administrator.');
      }
    } catch {
      setError('Cannot connect to server.');
    } finally {
      setLoading(false);
    }
  };

  // ─── Step 3: Set Password + Get QR ───
  const handleCreatePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 6) { setError('Password must be at least 6 characters'); return; }
    if (password !== confirmPassword) { setError('Passwords do not match'); return; }
    setError('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/auth/set-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, setup_code: setupCode, password }),
      });
      const data = await res.json();

      if (data.success) {
        setQrBase64(data.totp_qr_base64 || '');
        setTotpSecret(data.totp_secret || '');
        setStep('scan_qr');
      } else {
        setError(data.message || 'Failed to set password');
      }
    } catch {
      setError('Cannot connect to server.');
    } finally {
      setLoading(false);
    }
  };

  // ─── Step 4: Confirm TOTP ───
  const handleConfirmTotp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (totpCode.length !== 6) { setError('Enter the 6-digit code from your authenticator'); return; }
    setError('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/auth/confirm-totp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, totp_code: totpCode }),
      });
      const data = await res.json();

      if (data.success) {
        setStep('setup_complete');
      } else {
        setError('Invalid code. Make sure you scanned the QR code and enter the current 6-digit code.');
      }
    } catch {
      setError('Cannot connect to server.');
    } finally {
      setLoading(false);
    }
  };

  // ─── Normal Login: Password ───
  const handleLoginPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) { setError('Please enter your password'); return; }
    setError('');

    // Check if this is super admin without TOTP
    if (email === 'superadmin@reknew.ai') {
      setLoading(true);
      const success = await loginAdmin(email, password);
      setLoading(false);
      if (success) {
        navigate('/');
      } else {
        setError('Invalid password');
      }
      return;
    }

    // Regular employee — proceed to TOTP step
    setStep('login_totp');
  };

  // ─── Normal Login: TOTP ───
  const handleLoginTotp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (totpCode.length !== 6) { setError('Enter the 6-digit code from your authenticator'); return; }
    setError('');
    setLoading(true);

    const result = await loginWithApi(email, password, totpCode);

    if (result.success) {
      navigate('/');
    } else {
      setError(result.message);
    }
    setLoading(false);
  };

  // ─── Setup Complete → Go to Login ───
  const handleSetupComplete = () => {
    resetForm();
    setStep('login_password');
  };

  // ─── Step indicator ───
  const firstTimeSteps = ['setup_code', 'create_password', 'scan_qr', 'confirm_totp', 'setup_complete'];
  const currentStepNum = firstTimeSteps.indexOf(step) + 1;
  const totalSteps = 4; // not counting success screen

  // ─── UI ───
  const inputClass = cn(
    'w-full py-3 rounded-xl text-[14px] font-medium',
    'bg-warm-bg border border-[#E5E7EB]',
    'text-[#2F3437] placeholder:text-gray-400',
    'outline-none transition-all duration-150 font-sans',
    'focus:border-olive/40 focus:ring-2 focus:ring-olive/10',
  );

  return (
    <div className="min-h-screen flex items-center justify-center bg-warm-bg font-sans px-6 py-12">
      <div className="w-full max-w-[420px]">
        {/* Logo */}
        <div className="flex flex-col items-center mb-10">
          <div className="w-14 h-14 rounded-full border-2 border-olive/25 flex items-center justify-center mb-4 relative">
            <div className="w-6 h-6 rounded-full bg-olive" />
            <div className="absolute inset-[-5px] rounded-full border border-olive/12" />
            <div className="absolute -top-1 right-0.5 w-2.5 h-2.5 rounded-full bg-sage" />
          </div>
          <span className="text-2xl font-bold text-[#2F3437] tracking-tight">
            Reknew <span className="text-olive">Orbit</span>
          </span>
        </div>

        {/* Card */}
        <div className="bg-warm-card border border-[#E5E7EB] rounded-2xl p-8 shadow-card-md">

          {/* Back button (not on email step or setup complete) */}
          {step !== 'email' && step !== 'setup_complete' && step !== 'login_password' && (
            <button
              onClick={goBack}
              className="flex items-center gap-1.5 text-[13px] text-gray-500 hover:text-olive font-medium mb-5 transition-colors"
            >
              <ArrowLeft size={14} /> Back
            </button>
          )}

          {/* First-time progress bar */}
          {isFirstLogin && firstTimeSteps.includes(step) && step !== 'setup_complete' && (
            <div className="flex gap-1.5 mb-6">
              {Array.from({ length: totalSteps }).map((_, i) => (
                <div
                  key={i}
                  className={cn(
                    'h-1 flex-1 rounded-full transition-all',
                    i < currentStepNum ? 'bg-olive' : 'bg-[#E5E7EB]'
                  )}
                />
              ))}
            </div>
          )}

          {/* ═══ STEP: EMAIL ═══ */}
          {step === 'email' && (
            <>
              <div className="text-center mb-8">
                <h2 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1.5">Welcome back</h2>
                <p className="text-sm text-gray-500">Sign in to Reknew Orbit using your ReKnew email.</p>
              </div>
              {error && <div className="mb-5 px-4 py-3 rounded-xl bg-status-error/5 border border-status-error/15 text-[13px] text-status-error font-medium">{error}</div>}
              <form onSubmit={handleCheckEmail}>
                <label className="block text-[13px] font-semibold text-[#2F3437] mb-2">Email</label>
                <div className="relative mb-6">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"><Mail size={16} /></div>
                  <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@reknew.ai" required className={cn(inputClass, 'pl-10')} />
                </div>
                <button type="submit" disabled={loading} className={cn('w-full py-3.5 rounded-xl text-[15px] font-semibold text-white flex items-center justify-center gap-2 transition-all', loading ? 'bg-olive/60 cursor-not-allowed' : 'bg-olive hover:bg-olive-dark active:scale-[0.99] shadow-sm')}>
                  {loading && <Loader2 size={16} className="animate-spin" />}
                  {loading ? 'Checking...' : 'Continue'}
                </button>
              </form>
            </>
          )}

          {/* ═══ STEP: SETUP CODE ═══ */}
          {step === 'setup_code' && (
            <>
              <div className="text-center mb-8">
                <div className="w-12 h-12 rounded-full bg-olive/10 flex items-center justify-center mx-auto mb-4"><KeyRound size={22} className="text-olive" /></div>
                <h2 className="text-xl font-bold text-[#2F3437] tracking-tight mb-1.5">First-time setup</h2>
                <p className="text-sm text-gray-500">Enter the setup code provided by your administrator.</p>
              </div>
              {error && <div className="mb-5 px-4 py-3 rounded-xl bg-status-error/5 border border-status-error/15 text-[13px] text-status-error font-medium">{error}</div>}
              <form onSubmit={handleVerifySetupCode}>
                <label className="block text-[13px] font-semibold text-[#2F3437] mb-2">Setup Code</label>
                <input
                  value={setupCode}
                  onChange={(e) => setSetupCode(e.target.value.toUpperCase())}
                  placeholder="RK-XXX-0000"
                  required
                  className={cn(inputClass, 'px-4 text-center tracking-widest text-lg font-bold mb-2')}
                />
                <p className="text-[11px] text-gray-400 text-center mb-6">Example: RK-PEN-0695</p>
                <button type="submit" disabled={loading} className={cn('w-full py-3.5 rounded-xl text-[15px] font-semibold text-white flex items-center justify-center gap-2 transition-all', loading ? 'bg-olive/60 cursor-not-allowed' : 'bg-olive hover:bg-olive-dark active:scale-[0.99] shadow-sm')}>
                  {loading && <Loader2 size={16} className="animate-spin" />}
                  {loading ? 'Verifying...' : 'Verify Code'}
                </button>
              </form>
            </>
          )}

          {/* ═══ STEP: CREATE PASSWORD ═══ */}
          {step === 'create_password' && (
            <>
              <div className="text-center mb-8">
                <div className="w-12 h-12 rounded-full bg-olive/10 flex items-center justify-center mx-auto mb-4"><Lock size={22} className="text-olive" /></div>
                <h2 className="text-xl font-bold text-[#2F3437] tracking-tight mb-1.5">Create password</h2>
                <p className="text-sm text-gray-500">Choose a strong password for your account.</p>
              </div>
              {error && <div className="mb-5 px-4 py-3 rounded-xl bg-status-error/5 border border-status-error/15 text-[13px] text-status-error font-medium">{error}</div>}
              <form onSubmit={handleCreatePassword}>
                <label className="block text-[13px] font-semibold text-[#2F3437] mb-2">Password</label>
                <div className="relative mb-4">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"><Lock size={16} /></div>
                  <input type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Minimum 6 characters" required className={cn(inputClass, 'pl-10 pr-11')} />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors">
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <label className="block text-[13px] font-semibold text-[#2F3437] mb-2">Confirm Password</label>
                <div className="relative mb-6">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"><Lock size={16} /></div>
                  <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="Re-enter password" required className={cn(inputClass, 'pl-10')} />
                </div>
                <button type="submit" disabled={loading} className={cn('w-full py-3.5 rounded-xl text-[15px] font-semibold text-white flex items-center justify-center gap-2 transition-all', loading ? 'bg-olive/60 cursor-not-allowed' : 'bg-olive hover:bg-olive-dark active:scale-[0.99] shadow-sm')}>
                  {loading && <Loader2 size={16} className="animate-spin" />}
                  {loading ? 'Setting up...' : 'Set Password & Continue'}
                </button>
              </form>
            </>
          )}

          {/* ═══ STEP: SCAN QR ═══ */}
          {step === 'scan_qr' && (
            <>
              <div className="text-center mb-6">
                <div className="w-12 h-12 rounded-full bg-olive/10 flex items-center justify-center mx-auto mb-4"><QrCode size={22} className="text-olive" /></div>
                <h2 className="text-xl font-bold text-[#2F3437] tracking-tight mb-1.5">Set up authenticator</h2>
                <p className="text-sm text-gray-500">Scan this QR code with Microsoft Authenticator or any TOTP app.</p>
              </div>

              {/* QR Code */}
              {qrBase64 && (
                <div className="flex justify-center mb-5">
                  <div className="p-4 bg-white rounded-2xl border border-[#E5E7EB] shadow-card">
                    <img src={`data:image/png;base64,${qrBase64}`} alt="TOTP QR Code" className="w-48 h-48" />
                  </div>
                </div>
              )}

              {/* Manual entry fallback */}
              {totpSecret && (
                <div className="mb-6">
                  <p className="text-[11px] text-gray-400 text-center mb-2">Can't scan? Enter this code manually:</p>
                  <div className="bg-warm-bg border border-[#E5E7EB] rounded-xl px-4 py-3 text-center">
                    <code className="text-[13px] font-mono font-bold text-olive tracking-wider select-all">{totpSecret}</code>
                  </div>
                </div>
              )}

              <button
                onClick={() => { setTotpCode(''); setStep('confirm_totp'); }}
                className="w-full py-3.5 rounded-xl text-[15px] font-semibold text-white bg-olive hover:bg-olive-dark active:scale-[0.99] shadow-sm transition-all"
              >
                I've scanned it — Continue
              </button>
            </>
          )}

          {/* ═══ STEP: CONFIRM TOTP ═══ */}
          {step === 'confirm_totp' && (
            <>
              <div className="text-center mb-8">
                <div className="w-12 h-12 rounded-full bg-olive/10 flex items-center justify-center mx-auto mb-4"><Smartphone size={22} className="text-olive" /></div>
                <h2 className="text-xl font-bold text-[#2F3437] tracking-tight mb-1.5">Verify authenticator</h2>
                <p className="text-sm text-gray-500">Enter the 6-digit code from your authenticator app.</p>
              </div>
              {error && <div className="mb-5 px-4 py-3 rounded-xl bg-status-error/5 border border-status-error/15 text-[13px] text-status-error font-medium">{error}</div>}
              <form onSubmit={handleConfirmTotp}>
                <label className="block text-[13px] font-semibold text-[#2F3437] mb-2">Authenticator Code</label>
                <input
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  required
                  maxLength={6}
                  className={cn(inputClass, 'px-4 text-center tracking-[0.3em] text-2xl font-bold mb-6')}
                  autoFocus
                />
                <button type="submit" disabled={loading || totpCode.length !== 6} className={cn('w-full py-3.5 rounded-xl text-[15px] font-semibold text-white flex items-center justify-center gap-2 transition-all', loading || totpCode.length !== 6 ? 'bg-olive/60 cursor-not-allowed' : 'bg-olive hover:bg-olive-dark active:scale-[0.99] shadow-sm')}>
                  {loading && <Loader2 size={16} className="animate-spin" />}
                  {loading ? 'Verifying...' : 'Confirm & Complete Setup'}
                </button>
              </form>
            </>
          )}

          {/* ═══ STEP: SETUP COMPLETE ═══ */}
          {step === 'setup_complete' && (
            <div className="text-center py-4">
              <div className="w-16 h-16 rounded-full bg-status-success/10 flex items-center justify-center mx-auto mb-5">
                <CheckCircle size={32} className="text-status-success" />
              </div>
              <h2 className="text-xl font-bold text-[#2F3437] tracking-tight mb-2">You're all set!</h2>
              <p className="text-sm text-gray-500 mb-8 leading-relaxed">
                Your account is ready. You can now sign in with your email, password, and authenticator code.
              </p>
              <button
                onClick={handleSetupComplete}
                className="w-full py-3.5 rounded-xl text-[15px] font-semibold text-white bg-olive hover:bg-olive-dark active:scale-[0.99] shadow-sm transition-all"
              >
                Sign In Now
              </button>
            </div>
          )}

          {/* ═══ STEP: LOGIN PASSWORD ═══ */}
          {step === 'login_password' && (
            <>
              <div className="text-center mb-6">
                <h2 className="text-2xl font-bold text-[#2F3437] tracking-tight mb-1.5">Welcome back</h2>
                <p className="text-sm text-gray-500">{email}</p>
              </div>
              {error && <div className="mb-5 px-4 py-3 rounded-xl bg-status-error/5 border border-status-error/15 text-[13px] text-status-error font-medium">{error}</div>}
              <form onSubmit={handleLoginPassword}>
                <label className="block text-[13px] font-semibold text-[#2F3437] mb-2">Password</label>
                <div className="relative mb-6">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"><Lock size={16} /></div>
                  <input type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" required className={cn(inputClass, 'pl-10 pr-11')} autoFocus />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors">
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <button type="submit" disabled={loading} className={cn('w-full py-3.5 rounded-xl text-[15px] font-semibold text-white flex items-center justify-center gap-2 transition-all', loading ? 'bg-olive/60 cursor-not-allowed' : 'bg-olive hover:bg-olive-dark active:scale-[0.99] shadow-sm')}>
                  {loading && <Loader2 size={16} className="animate-spin" />}
                  {loading ? 'Signing in...' : 'Continue'}
                </button>
              </form>
            </>
          )}

          {/* ═══ STEP: LOGIN TOTP ═══ */}
          {step === 'login_totp' && (
            <>
              <div className="text-center mb-8">
                <div className="w-12 h-12 rounded-full bg-olive/10 flex items-center justify-center mx-auto mb-4"><Smartphone size={22} className="text-olive" /></div>
                <h2 className="text-xl font-bold text-[#2F3437] tracking-tight mb-1.5">Authenticator code</h2>
                <p className="text-sm text-gray-500">Enter the 6-digit code from Microsoft Authenticator.</p>
              </div>
              {error && <div className="mb-5 px-4 py-3 rounded-xl bg-status-error/5 border border-status-error/15 text-[13px] text-status-error font-medium">{error}</div>}
              <form onSubmit={handleLoginTotp}>
                <input
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  required
                  maxLength={6}
                  className={cn(inputClass, 'px-4 text-center tracking-[0.3em] text-2xl font-bold mb-6')}
                  autoFocus
                />
                <button type="submit" disabled={loading || totpCode.length !== 6} className={cn('w-full py-3.5 rounded-xl text-[15px] font-semibold text-white flex items-center justify-center gap-2 transition-all', loading || totpCode.length !== 6 ? 'bg-olive/60 cursor-not-allowed' : 'bg-olive hover:bg-olive-dark active:scale-[0.99] shadow-sm')}>
                  {loading && <Loader2 size={16} className="animate-spin" />}
                  {loading ? 'Signing in...' : 'Sign In'}
                </button>
              </form>
            </>
          )}

          {/* Footer */}
          {step === 'email' && (
            <div className="flex items-center gap-2.5 mt-6 pt-5 border-t border-[#E5E7EB]">
              <ShieldCheck size={16} className="text-olive shrink-0" />
              <span className="text-[12px] text-gray-400 font-medium">Only authorized ReKnew employees can access this system.</span>
            </div>
          )}
        </div>

        <p className="text-center mt-6 text-[11px] text-gray-400">© 2026 ReKnew · Privacy Policy · Terms of Service</p>
      </div>
    </div>
  );
}
