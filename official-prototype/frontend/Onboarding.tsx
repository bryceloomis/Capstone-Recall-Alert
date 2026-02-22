/**
 * Auth screen: Login / Sign Up with username + password.
 * On successful auth the user is routed to the profile-setup page (first time)
 * or straight to the main app (returning user).
 */
import { useState } from 'react';
import { useStore } from './store';
import { loginUser, registerUser } from './api';

type Mode = 'login' | 'signup';

export function Onboarding() {
  const login = useStore((s) => s.login);
  const setHasSeenOnboarding = useStore((s) => s.setHasSeenOnboarding);

  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!username.trim() || !password) {
      setError('Username and password are required.');
      return;
    }

    if (mode === 'signup' && password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    if (mode === 'signup' && password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }

    setLoading(true);
    try {
      const res =
        mode === 'signup'
          ? await registerUser({ username: username.trim(), password })
          : await loginUser({ username: username.trim(), password });

      login(res.token, res.user_id, res.username);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? (mode === 'login' ? 'Invalid username or password.' : 'Registration failed. Username may already be taken.');
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSkip = () => {
    setHasSeenOnboarding(true);
  };

  const inputClass =
    'w-full px-4 py-3 bg-transparent border border-black/5 rounded-xl text-[#1A1A1A] placeholder-[#888] focus:outline-none focus:border-black/15 hover:border-black/10 transition-colors duration-200';
  const btnPrimary =
    'w-full py-3 rounded-xl text-sm font-medium text-white bg-[#1A1A1A] hover:opacity-90 transition-opacity duration-200 disabled:opacity-50';
  const btnSecondary =
    'w-full py-3 rounded-xl text-sm font-medium text-[#1A1A1A] border border-black/10 hover:bg-[#1A1A1A] hover:text-white hover:border-[#1A1A1A] transition-colors duration-200';

  return (
    <div className="min-h-screen bg-cream flex flex-col">
      <div className="flex-1 flex flex-col justify-center px-6 py-12 max-w-md mx-auto w-full">
        <h1 className="text-2xl md:text-3xl font-semibold text-[#1A1A1A] tracking-tight">
          Food Recall Alert
        </h1>
        <p className="text-[#888] text-sm mt-2 mb-8">
          Check recalls, keep your groceries safe, and get personalized alerts based on your location and dietary needs.
        </p>

        {/* Tab switcher */}
        <div className="flex mb-6 border border-black/5 rounded-xl overflow-hidden">
          <button
            type="button"
            onClick={() => { setMode('login'); setError(''); }}
            className={`flex-1 py-2.5 text-sm font-medium transition-colors duration-200 ${
              mode === 'login' ? 'bg-[#1A1A1A] text-white' : 'text-[#888] hover:text-[#1A1A1A]'
            }`}
          >
            Log in
          </button>
          <button
            type="button"
            onClick={() => { setMode('signup'); setError(''); }}
            className={`flex-1 py-2.5 text-sm font-medium transition-colors duration-200 ${
              mode === 'signup' ? 'bg-[#1A1A1A] text-white' : 'text-[#888] hover:text-[#1A1A1A]'
            }`}
          >
            Sign up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 mb-6">
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Username"
            autoComplete="username"
            className={inputClass}
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            className={inputClass}
          />
          {mode === 'signup' && (
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm password"
              autoComplete="new-password"
              className={inputClass}
            />
          )}

          {error && (
            <p className="text-red-600 text-sm">{error}</p>
          )}

          <button type="submit" disabled={loading} className={btnPrimary}>
            {loading ? 'Please wait...' : mode === 'login' ? 'Log in' : 'Create account'}
          </button>
        </form>

        {/* Divider */}
        <div className="relative mb-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-black/5" />
          </div>
          <div className="relative flex justify-center">
            <span className="px-4 bg-cream text-[#888] text-sm font-medium">or</span>
          </div>
        </div>

        <button type="button" onClick={handleSkip} className={btnSecondary}>
          Try it out first
        </button>
        <p className="text-center text-[#888] text-xs mt-3">
          You can create an account later from Settings.
        </p>
      </div>
    </div>
  );
}
