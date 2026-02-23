/**
 * Top bar: logo, step arrows (when in V2 demo flow), nav links (MVP), Sign in, mode dropdown (MVP | V2: Ingredient preferences).
 */
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Home, Camera, ShoppingCart, Settings, ChevronDown, LogIn, ChevronLeft, ChevronRight } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { useStore } from './store';

const MVP_LINKS = [
  { path: '/', label: 'Home', Icon: Home },
  { path: '/scan', label: 'Scan', Icon: Camera },
  { path: '/groceries', label: 'My Groceries', Icon: ShoppingCart },
  { path: '/settings', label: 'Settings', Icon: Settings },
];

/** Ordered paths for the V2: Ingredient preferences step-through flow */
const V2_STEP_PATHS = [
  '/v2/demo',
  '/v2/demo/cart',
  '/v2/demo/recommendations',
  '/v2/demo/allergens',
  '/v2/demo/restrictions',
];
const V2_STEP_COUNT = V2_STEP_PATHS.length;

export function TopNav() {
  const location = useLocation();
  const navigate = useNavigate();
  const setHasSeenOnboarding = useStore((s) => s.setHasSeenOnboarding);
  const userProfile = useStore((s) => s.userProfile);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const isSignedIn = userProfile != null && (userProfile.name != null || userProfile.email != null);

  const isV2StepFlow = V2_STEP_PATHS.includes(location.pathname);
  const stepIndex = V2_STEP_PATHS.indexOf(location.pathname);
  const currentStep = stepIndex >= 0 ? stepIndex + 1 : 1;
  const links = isV2StepFlow ? [] : MVP_LINKS;

  const handleBackToSignIn = () => {
    setHasSeenOnboarding(false);
  };

  const handleSelectMode = (mode: 'mvp' | 'v2-preferences') => {
    setDropdownOpen(false);
    if (mode === 'mvp') navigate('/');
    else navigate(V2_STEP_PATHS[0]);
  };

  const dropdownLabel = isV2StepFlow ? 'V2: Ingredient preferences' : 'MVP';

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="bg-black text-white">
      <div className="max-w-6xl mx-auto px-4 flex items-center justify-between h-14 md:h-16">
        <Link to={isV2StepFlow ? V2_STEP_PATHS[0] : '/'} className="font-semibold text-white/90 hover:text-white tracking-tight text-[15px] transition-colors duration-200">
          Food Recall Alert
        </Link>

        {isV2StepFlow && (
          <div className="hidden md:flex items-center gap-4">
            <button
              type="button"
              onClick={() => navigate(V2_STEP_PATHS[Math.max(0, stepIndex - 1)])}
              disabled={currentStep === 1}
              className="p-2 text-white disabled:opacity-30 hover:opacity-90 transition-opacity"
              aria-label="Previous step"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <span className="text-sm text-white/80 min-w-[8rem] text-center">
              Step {currentStep} of {V2_STEP_COUNT}
            </span>
            <button
              type="button"
              onClick={() => navigate(V2_STEP_PATHS[Math.min(V2_STEP_COUNT - 1, stepIndex + 1)])}
              disabled={currentStep === V2_STEP_COUNT}
              className="p-2 text-white disabled:opacity-30 hover:opacity-90 transition-opacity"
              aria-label="Next step"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        )}

        <nav className="hidden md:flex items-center gap-8">
          {links.map(({ path, label, Icon }) => {
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
              onClick={handleBackToSignIn}
              className="flex items-center gap-2 text-sm font-medium text-white/50 hover:text-white transition-colors duration-200"
            >
              <LogIn className="w-4 h-4" />
              Sign in
            </button>
          )}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white/50 hover:text-white transition-colors duration-200"
            >
              {dropdownLabel}
              <ChevronDown className={`w-4 h-4 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
            </button>
            {dropdownOpen && (
              <div className="absolute right-0 top-full mt-1 py-1 w-44 bg-neutral-900 border border-neutral-700 rounded-lg shadow-lg z-50">
                <button
                  onClick={() => handleSelectMode('mvp')}
                  className={`w-full text-left px-4 py-2.5 text-sm font-medium transition-colors ${
                    !isV2StepFlow ? 'bg-white/10 text-white' : 'text-neutral-300 hover:bg-white/5 hover:text-white'
                  }`}
                >
                  MVP
                </button>
                <button
                  onClick={() => handleSelectMode('v2-preferences')}
                  className={`w-full text-left px-4 py-2.5 text-sm font-medium transition-colors ${
                    isV2StepFlow ? 'bg-white/10 text-white' : 'text-neutral-300 hover:bg-white/5 hover:text-white'
                  }`}
                >
                  V2: Ingredient preferences
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Mobile: V2 step arrows */}
      {isV2StepFlow && (
        <div className="md:hidden flex items-center justify-center gap-4 py-3 border-t border-white/10">
          <button
            type="button"
            onClick={() => navigate(V2_STEP_PATHS[Math.max(0, stepIndex - 1)])}
            disabled={currentStep === 1}
            className="p-2 text-white disabled:opacity-30"
            aria-label="Previous step"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <span className="text-sm text-white/80">Step {currentStep} of {V2_STEP_COUNT}</span>
          <button
            type="button"
            onClick={() => navigate(V2_STEP_PATHS[Math.min(V2_STEP_COUNT - 1, stepIndex + 1)])}
            disabled={currentStep === V2_STEP_COUNT}
            className="p-2 text-white disabled:opacity-30"
            aria-label="Next step"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Mobile: nav links as a second row */}
      <nav className="md:hidden flex items-center justify-around border-t border-white/10 h-12 px-2">
        {links.map(({ path, label, Icon }) => {
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
