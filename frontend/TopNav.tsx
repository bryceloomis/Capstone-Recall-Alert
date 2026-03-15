/**
 * Top bar: logo, nav links, user account / sign-in.
 */
import { Link, useLocation } from 'react-router-dom';
import { Home, Camera, ShoppingCart, Settings, LogIn } from 'lucide-react';
import { useStore } from './store';

const NAV_LINKS = [
  { path: '/', label: 'Home', Icon: Home },
  { path: '/scan', label: 'Scan', Icon: Camera },
  { path: '/groceries', label: 'My Groceries', Icon: ShoppingCart },
  { path: '/settings', label: 'Settings', Icon: Settings },
];

export function TopNav() {
  const location = useLocation();
  const setHasSeenOnboarding = useStore((s) => s.setHasSeenOnboarding);
  const userProfile = useStore((s) => s.userProfile);
  const isSignedIn = userProfile != null && (userProfile.name != null || userProfile.email != null);

  return (
    <header className="bg-black text-white">
      <div className="max-w-6xl mx-auto px-4 flex items-center justify-between h-14 md:h-16">
        <Link to="/" className="font-semibold text-white/90 hover:text-white tracking-tight text-[15px] transition-colors duration-200">
          Food Recall Alert
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {NAV_LINKS.map(({ path, label, Icon }) => {
            const active = location.pathname === path;
            return (
              <Link
                key={path}
                to={path}
                className={`flex items-center gap-2 text-sm font-medium transition-colors duration-200 border-b border-transparent hover:border-white ${
                  active ? 'text-white border-white' : 'text-white/50 hover:text-white'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-4">
          {isSignedIn ? (
            <Link
              to="/settings"
              className="text-sm text-white/70 hover:text-white transition-colors duration-200 hidden md:block"
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

      {/* Mobile nav */}
      <nav className="md:hidden flex items-center justify-around border-t border-white/10 h-12 px-2">
        {NAV_LINKS.map(({ path, label, Icon }) => {
          const active = location.pathname === path;
          return (
            <Link
              key={path}
              to={path}
              className={`flex flex-col items-center justify-center gap-0.5 py-2 px-3 text-xs font-medium transition-colors duration-200 ${
                active ? 'text-white' : 'text-white/50 hover:text-white'
              }`}
            >
              <Icon className="w-5 h-5" />
              {label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
