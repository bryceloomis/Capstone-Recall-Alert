/**
 * Onboarding: multi-step account creation.
 * 1. Auth (name, email, password)  →  2. State + allergens  →  3. Diets + custom ingredients  →  account created
 */
import { useState } from 'react';
import { ChevronRight, ChevronLeft, Check, Plus, X } from 'lucide-react';
import { useStore } from './store';
import { registerUser, loginUser } from './api';
import { COMMON_ALLERGENS, COMMON_DIETS, US_STATES } from './types';

type Step = 'auth' | 'allergens' | 'diets';
type AuthTab = 'create' | 'signin';

export function Onboarding() {
  const setHasSeenOnboarding = useStore((s) => s.setHasSeenOnboarding);
  const setUserId = useStore((s) => s.setUserId);
  const setUserProfile = useStore((s) => s.setUserProfile);
  const setAllergens = useStore((s) => s.setAllergens);
  const setDietPreferences = useStore((s) => s.setDietPreferences);

  const [step, setStep] = useState<Step>('auth');
  const [authTab, setAuthTab] = useState<AuthTab>('create');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [usState, setUsState] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [selectedAllergens, setSelectedAllergens] = useState<string[]>([]);
  const [selectedDiets, setSelectedDiets] = useState<string[]>([]);
  const [customIngredients, setCustomIngredients] = useState<string[]>([]);
  const [ingredientInput, setIngredientInput] = useState('');

  const toggleItem = (list: string[], item: string, setter: (v: string[]) => void) => {
    setter(list.includes(item) ? list.filter(x => x !== item) : [...list, item]);
  };

  const addCustomIngredient = () => {
    const trimmed = ingredientInput.trim();
    if (!trimmed) return;
    const normalized = trimmed.charAt(0).toUpperCase() + trimmed.slice(1).toLowerCase();
    if (!selectedAllergens.includes(normalized) && !customIngredients.includes(normalized)) {
      setCustomIngredients(prev => [...prev, normalized]);
    }
    setIngredientInput('');
  };

  const removeCustomIngredient = (item: string) => {
    setCustomIngredients(prev => prev.filter(x => x !== item));
  };

  const handleSkip = () => setHasSeenOnboarding(true);

  const allAllergens = [...selectedAllergens, ...customIngredients];

  const handleCreateAccount = async () => {
    setError(null);
    setLoading(true);
    try {
      const user = await registerUser(name, email, password, allAllergens, selectedDiets, usState || undefined);
      setUserId(String(user.id));
      setUserProfile({
        id: user.id, name: user.name, email: user.email,
        allergens: user.allergens, diet_preferences: user.diet_preferences,
      });
      setAllergens(user.allergens ?? allAllergens);
      setDietPreferences(user.diet_preferences ?? selectedDiets);
      setHasSeenOnboarding(true);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      if (msg?.includes('already exists')) {
        try {
          const user = await loginUser(email, password);
          setUserId(String(user.id));
          setUserProfile({ id: user.id, name: user.name, email: user.email, allergens: user.allergens, diet_preferences: user.diet_preferences });
          setAllergens(user.allergens ?? []);
          setDietPreferences(user.diet_preferences ?? []);
          setHasSeenOnboarding(true);
        } catch { setError('Account exists but password is incorrect.'); }
      } else {
        setError(msg ?? 'Something went wrong. Please try again.');
      }
    } finally { setLoading(false); }
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) { setError('Please enter your email and password.'); return; }
    setError(null);
    setLoading(true);
    try {
      const user = await loginUser(email, password);
      setUserId(String(user.id));
      setUserProfile({ id: user.id, name: user.name, email: user.email, allergens: user.allergens, diet_preferences: user.diet_preferences });
      setAllergens(user.allergens ?? []);
      setDietPreferences(user.diet_preferences ?? []);
      setHasSeenOnboarding(true);
    } catch { setError('Invalid email or password.'); }
    finally { setLoading(false); }
  };

  const inputClass = 'w-full px-4 py-3 bg-transparent border border-black/5 rounded-xl text-[#1A1A1A] placeholder-[#888] focus:outline-none focus:border-black/15 hover:border-black/10 transition-colors duration-200';
  const chipClass = (selected: boolean) =>
    `px-4 py-2 rounded-full text-sm font-medium border transition-all duration-200 ${
      selected
        ? 'bg-[#1A1A1A] text-white border-[#1A1A1A]'
        : 'bg-white text-[#555] border-black/10 hover:border-black/20'
    }`;

  /* ── Step 2: Allergens + US State ── */
  if (step === 'allergens') {
    return (
      <div className="min-h-screen bg-cream flex flex-col">
        <div className="flex-1 flex flex-col justify-center px-6 py-12 max-w-md mx-auto w-full">
          <button onClick={() => setStep('auth')} className="flex items-center gap-1 text-sm text-[#888] mb-6 hover:text-black transition-colors">
            <ChevronLeft className="w-4 h-4" /> Back
          </button>

          {/* US State */}
          <h2 className="text-2xl font-semibold text-[#1A1A1A] mb-2">Where are you located?</h2>
          <p className="text-sm text-[#888] mb-4">We'll prioritize recalls relevant to your state.</p>
          <select
            value={usState}
            onChange={e => setUsState(e.target.value)}
            className={`${inputClass} mb-8 appearance-none bg-white`}
          >
            <option value="">Select state (optional)</option>
            {US_STATES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>

          {/* Allergens */}
          <h2 className="text-2xl font-semibold text-[#1A1A1A] mb-2">Any allergies?</h2>
          <p className="text-sm text-[#888] mb-4">We'll flag products that contain these.</p>
          <div className="flex flex-wrap gap-2 mb-4">
            {COMMON_ALLERGENS.map(a => (
              <button key={a} onClick={() => toggleItem(selectedAllergens, a, setSelectedAllergens)} className={chipClass(selectedAllergens.includes(a))}>
                {selectedAllergens.includes(a) && <Check className="w-3.5 h-3.5 inline mr-1" />}{a}
              </button>
            ))}
          </div>

          {/* Custom ingredient entry */}
          <p className="text-sm text-[#888] mb-2">Or add specific ingredients to avoid:</p>
          <div className="flex gap-2 mb-3">
            <input
              type="text"
              value={ingredientInput}
              onChange={e => setIngredientInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCustomIngredient(); } }}
              placeholder="e.g. Red Dye 40"
              className={`${inputClass} flex-1`}
            />
            <button
              type="button"
              onClick={addCustomIngredient}
              className="px-3 py-2 rounded-xl border border-black/10 text-[#888] hover:bg-black hover:text-white hover:border-black transition-colors duration-200"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
          {customIngredients.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-4">
              {customIngredients.map(item => (
                <span key={item} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium bg-[#1A1A1A] text-white">
                  {item}
                  <button type="button" onClick={() => removeCustomIngredient(item)} className="hover:opacity-70"><X className="w-3.5 h-3.5" /></button>
                </span>
              ))}
            </div>
          )}

          <div className="flex gap-3 mt-4">
            <button onClick={() => setStep('diets')} className="flex-1 py-3 rounded-xl text-sm font-medium bg-[#1A1A1A] text-white hover:opacity-90 transition-opacity flex items-center justify-center gap-2">
              Next <ChevronRight className="w-4 h-4" />
            </button>
            <button onClick={() => { setSelectedAllergens([]); setCustomIngredients([]); setStep('diets'); }} className="px-4 py-3 rounded-xl text-sm font-medium text-[#888] border border-black/10 hover:bg-black/5 transition-colors">
              Skip
            </button>
          </div>
        </div>
      </div>
    );
  }

  /* ── Step 3: Dietary preferences → create account ── */
  if (step === 'diets') {
    return (
      <div className="min-h-screen bg-cream flex flex-col">
        <div className="flex-1 flex flex-col justify-center px-6 py-12 max-w-md mx-auto w-full">
          <button onClick={() => setStep('allergens')} className="flex items-center gap-1 text-sm text-[#888] mb-6 hover:text-black transition-colors">
            <ChevronLeft className="w-4 h-4" /> Back
          </button>
          <h2 className="text-2xl font-semibold text-[#1A1A1A] mb-2">Dietary preferences?</h2>
          <p className="text-sm text-[#888] mb-6">We'll check ingredients against your diet. You can change this later in Settings.</p>
          <div className="flex flex-wrap gap-2 mb-8">
            {COMMON_DIETS.map(d => (
              <button key={d} onClick={() => toggleItem(selectedDiets, d, setSelectedDiets)} className={chipClass(selectedDiets.includes(d))}>
                {selectedDiets.includes(d) && <Check className="w-3.5 h-3.5 inline mr-1" />}{d}
              </button>
            ))}
          </div>
          <button onClick={handleCreateAccount} disabled={loading}
            className="w-full py-3 rounded-xl text-sm font-medium bg-[#1A1A1A] text-white hover:opacity-90 transition-opacity disabled:opacity-50">
            {loading ? 'Creating account…' : 'Create account'}
          </button>
          {error && <p className="text-red-500 text-sm mt-3">{error}</p>}
        </div>
      </div>
    );
  }

  /* ── Step 1: Auth (create / sign in) ── */
  return (
    <div className="min-h-screen bg-cream flex flex-col">
      <div className="flex-1 flex flex-col justify-center px-6 py-12 max-w-md mx-auto w-full">
        <h1 className="text-2xl md:text-3xl font-semibold text-[#1A1A1A] tracking-tight">Food Recall Alert</h1>
        <p className="text-[#888] text-sm mt-2 mb-8">Check recalls, allergens, and diet conflicts instantly.</p>

        <div className="flex rounded-xl border border-black/10 p-1 mb-6 bg-white">
          <button type="button" onClick={() => { setAuthTab('create'); setError(null); }}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors duration-200 ${authTab === 'create' ? 'bg-[#1A1A1A] text-white' : 'text-[#888] hover:text-[#1A1A1A]'}`}>
            Create account
          </button>
          <button type="button" onClick={() => { setAuthTab('signin'); setError(null); }}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors duration-200 ${authTab === 'signin' ? 'bg-[#1A1A1A] text-white' : 'text-[#888] hover:text-[#1A1A1A]'}`}>
            Sign in
          </button>
        </div>

        {authTab === 'create' && (
          <form onSubmit={(e) => { e.preventDefault(); if (name && email && password) setStep('allergens'); else setError('Please fill in all fields.'); }} className="space-y-4 mb-8">
            <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Name" className={inputClass} autoComplete="name" required />
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" className={inputClass} autoComplete="email" required />
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password" className={inputClass} autoComplete="new-password" required />
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <button type="submit"
              className="w-full py-3 rounded-xl text-sm font-medium text-[#1A1A1A] border border-black/10 hover:bg-[#1A1A1A] hover:text-white hover:border-[#1A1A1A] transition-colors duration-200 flex items-center justify-center gap-2">
              Continue <ChevronRight className="w-4 h-4" />
            </button>
          </form>
        )}

        {authTab === 'signin' && (
          <form onSubmit={handleSignIn} className="space-y-4 mb-8">
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" className={inputClass} autoComplete="email" required />
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password" className={inputClass} autoComplete="current-password" required />
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <button type="submit" disabled={loading}
              className="w-full py-3 rounded-xl text-sm font-medium text-[#1A1A1A] border border-black/10 hover:bg-[#1A1A1A] hover:text-white hover:border-[#1A1A1A] transition-colors duration-200 disabled:opacity-50">
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        )}

        <div className="relative">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-black/5" /></div>
          <div className="relative flex justify-center"><span className="px-4 bg-cream text-[#888] text-sm font-medium">or</span></div>
        </div>
        <button type="button" onClick={handleSkip}
          className="mt-6 w-full py-3 rounded-xl text-sm font-medium text-[#1A1A1A] border border-black/10 hover:bg-[#1A1A1A] hover:text-white hover:border-[#1A1A1A] transition-colors duration-200">
          Try it out first
        </button>
        <p className="text-center text-[#888] text-xs mt-3">You can create an account later from Settings.</p>
      </div>
    </div>
  );
}
