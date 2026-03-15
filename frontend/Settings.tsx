/**
 * Settings: account info, state, allergen/diet/ingredient profile, notifications, and sign-out.
 */
import { useState, useEffect } from 'react';
import { User, Bell, Shield, Info, LogOut, Wheat, Leaf, Loader2, Check, MapPin, Plus, X } from 'lucide-react';
import { useStore } from './store';
import { getUserProfile, updateUserProfile } from './api';
import { COMMON_ALLERGENS, COMMON_DIETS, US_STATES } from './types';

export const Settings = () => {
  const userId = useStore((s) => s.userId);
  const setUserId = useStore((s) => s.setUserId);
  const setHasSeenOnboarding = useStore((s) => s.setHasSeenOnboarding);
  const userProfile = useStore((s) => s.userProfile);
  const setUserProfile = useStore((s) => s.setUserProfile);
  const allergens = useStore((s) => s.allergens);
  const setAllergens = useStore((s) => s.setAllergens);
  const dietPreferences = useStore((s) => s.dietPreferences);
  const setDietPreferences = useStore((s) => s.setDietPreferences);

  const isSignedIn = userProfile != null && (userProfile.name != null || userProfile.email != null);
  // userProfile.id may be missing in old sessions; userId in store is the string fallback
  const resolvedId = userProfile?.id ?? (userId && userId !== 'test_user' ? parseInt(userId) : undefined);

  const [localAllergens, setLocalAllergens] = useState<string[]>(allergens);
  const [localDiets, setLocalDiets] = useState<string[]>(dietPreferences);
  const [localState, setLocalState] = useState<string>('');
  const [customIngredients, setCustomIngredients] = useState<string[]>([]);
  const [ingredientInput, setIngredientInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(false);

  const [notifications, setNotifications] = useState({
    inApp: true, push: false, urgencyThreshold: 'all' as 'all' | 'class1_only',
  });

  useEffect(() => {
    if (!isSignedIn || !resolvedId) return;
    setLoadingProfile(true);
    getUserProfile(resolvedId)
      .then((p) => {
        // Patch userProfile in store if id was missing
        if (!userProfile?.id && p.id) {
          setUserProfile({ ...userProfile, id: p.id });
        }
        if (p.allergens) {
          const known = COMMON_ALLERGENS as readonly string[];
          const standard = p.allergens.filter((a: string) => known.includes(a));
          const custom = p.allergens.filter((a: string) => !known.includes(a));
          setLocalAllergens(standard);
          setCustomIngredients(custom);
          setAllergens(p.allergens);
        }
        if (p.diet_preferences) { setLocalDiets(p.diet_preferences); setDietPreferences(p.diet_preferences); }
        if (p.state) setLocalState(p.state);
      })
      .catch(() => {})
      .finally(() => setLoadingProfile(false));
  }, [resolvedId]);

  const toggleChip = (list: string[], item: string, setter: (v: string[]) => void) => {
    setter(list.includes(item) ? list.filter(x => x !== item) : [...list, item]);
    setSaved(false);
  };

  const addCustomIngredient = () => {
    const trimmed = ingredientInput.trim();
    if (!trimmed) return;
    const normalized = trimmed.charAt(0).toUpperCase() + trimmed.slice(1).toLowerCase();
    if (!localAllergens.includes(normalized) && !customIngredients.includes(normalized)) {
      setCustomIngredients(prev => [...prev, normalized]);
      setSaved(false);
    }
    setIngredientInput('');
  };

  const removeCustomIngredient = (item: string) => {
    setCustomIngredients(prev => prev.filter(x => x !== item));
    setSaved(false);
  };

  const allAllergens = [...localAllergens, ...customIngredients];

  const handleSaveProfile = async () => {
    if (!resolvedId) return;
    setSaving(true);
    try {
      await updateUserProfile(resolvedId, {
        allergens: allAllergens,
        diet_preferences: localDiets,
        state: localState || undefined,
      });
      setAllergens(allAllergens);
      setDietPreferences(localDiets);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch { alert('Failed to save. Please try again.'); }
    finally { setSaving(false); }
  };

  const handleSignOut = () => {
    setUserProfile(null);
    setUserId('test_user');
    setAllergens([]);
    setDietPreferences([]);
    setHasSeenOnboarding(false);
  };

  const sectionClass = 'mb-6 border border-black/5 rounded-xl p-6 bg-white';
  const headingClass = 'flex items-center gap-3 mb-4';
  const iconClass = 'w-5 h-5 text-[#888]';
  const inputClass = 'w-full px-4 py-3 bg-transparent border border-black/5 rounded-xl text-[#1A1A1A] placeholder-[#888] focus:outline-none focus:border-black/15 hover:border-black/10 transition-colors duration-200';
  const chipClass = (selected: boolean) =>
    `px-3.5 py-2 rounded-full text-sm font-medium border transition-all duration-200 ${
      selected ? 'bg-[#1A1A1A] text-white border-[#1A1A1A]' : 'bg-white text-[#555] border-black/10 hover:border-black/20'
    }`;

  return (
    <div className="max-w-2xl mx-auto space-y-2">
      <h2 className="text-xl font-semibold text-black mb-6">Settings</h2>

      {/* Account */}
      <section className={sectionClass}>
        <div className={headingClass}>
          <User className={iconClass} />
          <h3 className="text-lg font-semibold text-black">Account</h3>
        </div>
        {isSignedIn ? (
          <div className="space-y-3">
            <div>
              <p className="text-xs text-[#888] mb-0.5">Name</p>
              <p className="text-sm font-medium text-black">{userProfile!.name ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-[#888] mb-0.5">Email</p>
              <p className="text-sm font-medium text-black">{userProfile!.email ?? '—'}</p>
            </div>
          </div>
        ) : (
          <div className="text-center py-2">
            <p className="text-sm text-[#888] mb-3">Sign in to sync your profile and preferences.</p>
            <button onClick={() => setHasSeenOnboarding(false)}
              className="px-5 py-2.5 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity">
              Sign in or create account
            </button>
          </div>
        )}
      </section>

      {/* Location */}
      <section className={sectionClass}>
        <div className={headingClass}>
          <MapPin className={iconClass} />
          <h3 className="text-lg font-semibold text-black">Location</h3>
        </div>
        <p className="text-sm text-[#888] mb-3">Recalls are sometimes region-specific. Select your state to get relevant alerts.</p>
        <select
          value={localState}
          onChange={e => { setLocalState(e.target.value); setSaved(false); }}
          className={`${inputClass} appearance-none bg-white`}
        >
          <option value="">Select state (optional)</option>
          {US_STATES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </section>

      {/* Allergens + Custom Ingredients */}
      <section className={sectionClass}>
        <div className={headingClass}>
          <Wheat className={iconClass} />
          <h3 className="text-lg font-semibold text-black">Allergens</h3>
        </div>
        {loadingProfile ? (
          <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-[#888]" /></div>
        ) : (
          <>
            <p className="text-sm text-[#888] mb-3">Products containing these will be flagged during scans.</p>
            <div className="flex flex-wrap gap-2 mb-4">
              {COMMON_ALLERGENS.map(a => (
                <button key={a} onClick={() => toggleChip(localAllergens, a, setLocalAllergens)} className={chipClass(localAllergens.includes(a))}>
                  {localAllergens.includes(a) && <Check className="w-3 h-3 inline mr-1" />}{a}
                </button>
              ))}
            </div>

            <p className="text-sm text-[#888] mb-2">Custom ingredients to avoid:</p>
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
          </>
        )}
      </section>

      {/* Diets */}
      <section className={sectionClass}>
        <div className={headingClass}>
          <Leaf className={iconClass} />
          <h3 className="text-lg font-semibold text-black">Dietary preferences</h3>
        </div>
        {loadingProfile ? (
          <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-[#888]" /></div>
        ) : (
          <>
            <p className="text-sm text-[#888] mb-3">Ingredients incompatible with your diet will be flagged.</p>
            <div className="flex flex-wrap gap-2 mb-4">
              {COMMON_DIETS.map(d => (
                <button key={d} onClick={() => toggleChip(localDiets, d, setLocalDiets)} className={chipClass(localDiets.includes(d))}>
                  {localDiets.includes(d) && <Check className="w-3 h-3 inline mr-1" />}{d}
                </button>
              ))}
            </div>
          </>
        )}

        {isSignedIn && (
          <button onClick={handleSaveProfile} disabled={saving}
            className={`w-full py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
              saved ? 'bg-emerald-600 text-white' : 'bg-black text-white hover:opacity-90'
            } disabled:opacity-50`}>
            {saving ? 'Saving…' : saved ? 'Saved' : 'Save preferences'}
          </button>
        )}
      </section>

      {/* Notifications */}
      <section className={sectionClass}>
        <div className={headingClass}>
          <Bell className={iconClass} />
          <h3 className="text-lg font-semibold text-black">Notifications</h3>
        </div>
        <div className="space-y-4">
          <label className="flex items-center justify-between">
            <span className="text-black text-sm">In-app notifications</span>
            <input type="checkbox" checked={notifications.inApp}
              onChange={(e) => setNotifications({ ...notifications, inApp: e.target.checked })}
              className="w-4 h-4 rounded border-black/20 text-black focus:ring-black/20" />
          </label>
          <label className="flex items-center justify-between">
            <span className="text-black text-sm">Browser push notifications</span>
            <input type="checkbox" checked={notifications.push}
              onChange={(e) => setNotifications({ ...notifications, push: e.target.checked })}
              className="w-4 h-4 rounded border-black/20 text-black focus:ring-black/20" />
          </label>
          <div>
            <label className="block text-sm font-medium text-black mb-2">Urgency threshold</label>
            <select value={notifications.urgencyThreshold}
              onChange={(e) => setNotifications({ ...notifications, urgencyThreshold: e.target.value as 'all' | 'class1_only' })}
              className="w-full px-4 py-2.5 bg-cream border border-black/10 rounded-xl text-black focus:outline-none focus:border-black/20">
              <option value="all">All recalls</option>
              <option value="class1_only">Class I only (most serious)</option>
            </select>
          </div>
        </div>
      </section>

      {/* Privacy */}
      <section className={sectionClass}>
        <div className={headingClass}>
          <Shield className={iconClass} />
          <h3 className="text-lg font-semibold text-black">Privacy & data</h3>
        </div>
        <div className="space-y-2 text-sm text-[#888]">
          <p>Your allergen and diet preferences are stored on the server with your account.</p>
          <p>Scan results are not stored unless you add items to your grocery list.</p>
        </div>
      </section>

      {/* About */}
      <section className={sectionClass}>
        <div className={headingClass}>
          <Info className={iconClass} />
          <h3 className="text-lg font-semibold text-black">About</h3>
        </div>
        <div className="space-y-2 text-sm text-[#888]">
          <p><span className="font-medium text-black">Version:</span> 2.0.0</p>
          <p><span className="font-medium text-black">Project:</span> UC Berkeley MIDS Capstone</p>
          <p><span className="font-medium text-black">Data:</span> FDA/USDA recalls, Open Food Facts, AI risk analysis</p>
        </div>
      </section>

      {/* Sign out */}
      <section className={sectionClass}>
        {isSignedIn ? (
          <button onClick={handleSignOut}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 border border-black/10 text-black rounded-xl text-sm font-medium hover:bg-black hover:text-white hover:border-black transition-colors duration-200">
            <LogOut className="w-4 h-4" /> Sign out
          </button>
        ) : (
          <div className="text-center space-y-2">
            <button onClick={() => setHasSeenOnboarding(false)}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity">
              Sign in or create account
            </button>
            <p className="text-xs text-[#888]">Return to the sign-in page.</p>
          </div>
        )}
      </section>
    </div>
  );
};
