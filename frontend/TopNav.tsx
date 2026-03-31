/**
 * Top bar: logo + account/sign-in. Navigation lives in Layout (sidebar + bottom bar).
 */
import { Link } from 'react-router-dom';
import { LogIn } from 'lucide-react';
import { useStore } from './store';

export function TopNav() {
  const setHasSeenOnboarding = useStore((s) => s.setHasSeenOnboarding);
  const userProfile = useStore((s) => s.userProfile);
  const isSignedIn = userProfile != null && (userProfile.name != null || userProfile.email != null);

  return (
    <header className="bg-black text-white">
      <div className="max-w-6xl mx-auto px-4 flex items-center justify-between h-14 md:h-16">
        <Link to="/" className="font-semibold text-white/90 hover:text-white tracking-tight text-[15px] transition-colors duration-200">
          Food Recall Alert
        </Link>

        <div className="flex items-center gap-4">
          {isSignedIn ? (
            <Link
              to="/settings"
              className="text-sm text-white/70 hover:text-white transition-colors duration-200"
              title="Account settings"
            >
              {userProfile!.name ?? userProfile!.email}
            </Link>
          ) : (
            <button
              type="button"
              onClick={() => setHasSeenOnboarding(false)}
              className="flex items-center gap-2 text-sm font-medium text-white/50 hover:text-white transition-colors duration-200"
            >
              <LogIn className="w-4 h-4" />
              Sign in
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
