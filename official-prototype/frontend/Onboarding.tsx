/**
 * First-time entry: create account form + "Try it out first". Sets hasSeenOnboarding then shows main app.
 */
import { useState } from 'react';
import { useStore } from './store';

export function Onboarding() {
  const setHasSeenOnboarding = useStore((s) => s.setHasSeenOnboarding);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSkip = () => {
    setHasSeenOnboarding(true);
  };

  const handleCreateAccount = (e: React.FormEvent) => {
    e.preventDefault();
    // Not functional yet – just skip into the app for now
    setHasSeenOnboarding(true);
  };

  const inputClass =
    'w-full px-4 py-3 bg-transparent border border-black/5 rounded-xl text-[#1A1A1A] placeholder-[#888] focus:outline-none focus:border-black/15 hover:border-black/10 transition-colors duration-200';

  return (
    <div className="min-h-screen bg-cream flex flex-col">
      <div className="flex-1 flex flex-col justify-center px-6 py-12 max-w-md mx-auto w-full">
        <h1 className="text-2xl md:text-3xl font-semibold text-[#1A1A1A] tracking-tight">
          Food Recall Alert
        </h1>
        <p className="text-[#888] text-sm mt-2 mb-10">
          Check recalls and keep your groceries safe. Create an account to save your list and get personalized alerts, or try it out first.
        </p>

        <form onSubmit={handleCreateAccount} className="space-y-4 mb-8">
          <h2 className="text-sm font-semibold text-[#1A1A1A]">Create an account</h2>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name"
            className={inputClass}
          />
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            className={inputClass}
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            className={inputClass}
          />
          <button
            type="submit"
            className="w-full py-3 rounded-xl text-sm font-medium text-[#1A1A1A] border border-black/10 hover:bg-[#1A1A1A] hover:text-white hover:border-[#1A1A1A] transition-colors duration-200"
          >
            Create account
          </button>
        </form>

        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-black/5" />
          </div>
          <div className="relative flex justify-center">
            <span className="px-4 bg-cream text-[#888] text-sm font-medium">or</span>
          </div>
        </div>

        <button
          type="button"
          onClick={handleSkip}
          className="mt-6 w-full py-3 rounded-xl text-sm font-medium text-[#1A1A1A] border border-black/10 hover:bg-[#1A1A1A] hover:text-white hover:border-[#1A1A1A] transition-colors duration-200"
        >
          Try it out first
        </button>
        <p className="text-center text-[#888] text-xs mt-3">
          You can create an account later from Settings.
        </p>
      </div>
    </div>
  );
}
