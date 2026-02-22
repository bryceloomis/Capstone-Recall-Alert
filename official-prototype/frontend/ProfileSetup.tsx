/**
 * Secondary profile page shown after registration (or accessible via Settings / nav).
 * - State location: matches the user to relevant food recalls by geography.
 * - Allergies: common allergens the user can toggle.
 * - Diet preferences: dietary restrictions used when scanning / adding products to cart.
 *
 * Data is saved to the backend (`PUT /api/user/profile/:id`) and persisted in the
 * `user_preferences` table in AWS RDS.
 */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapPin, AlertTriangle, Leaf } from 'lucide-react';
import { useStore } from './store';
import { updateUserPreferences, getUserProfile } from './api';

/* ── Static data ── */

const US_STATES = [
  'Alabama','Alaska','Arizona','Arkansas','California','Colorado','Connecticut',
  'Delaware','Florida','Georgia','Hawaii','Idaho','Illinois','Indiana','Iowa',
  'Kansas','Kentucky','Louisiana','Maine','Maryland','Massachusetts','Michigan',
  'Minnesota','Mississippi','Missouri','Montana','Nebraska','Nevada','New Hampshire',
  'New Jersey','New Mexico','New York','North Carolina','North Dakota','Ohio',
  'Oklahoma','Oregon','Pennsylvania','Rhode Island','South Carolina','South Dakota',
  'Tennessee','Texas','Utah','Vermont','Virginia','Washington','West Virginia',
  'Wisconsin','Wyoming','District of Columbia','Puerto Rico','Guam',
  'U.S. Virgin Islands','American Samoa','Northern Mariana Islands',
];

const COMMON_ALLERGENS = [
  'Peanuts','Tree nuts','Milk','Eggs','Fish','Shellfish','Soy','Wheat','Sesame',
];

const DIET_OPTIONS = [
  'Vegetarian','Vegan','Gluten-free','Dairy-free','Keto','Paleo',
  'Halal','Kosher','Low sodium','Sugar-free',
];

export function ProfileSetup() {
  const navigate = useNavigate();
  const authUserId = useStore((s) => s.authUserId);
  const isAuthenticated = useStore((s) => s.isAuthenticated);
  const setHasCompletedProfile = useStore((s) => s.setHasCompletedProfile);
  const setUserPreferences = useStore((s) => s.setUserPreferences);
  const existingPrefs = useStore((s) => s.userPreferences);

  const [stateLocation, setStateLocation] = useState(existingPrefs?.state_location ?? '');
  const [selectedAllergens, setSelectedAllergens] = useState<Set<string>>(
    new Set(existingPrefs?.allergies ?? []),
  );
  const [customAllergen, setCustomAllergen] = useState('');
  const [selectedDiets, setSelectedDiets] = useState<Set<string>>(
    new Set(existingPrefs?.diet_preferences ?? []),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [loadingProfile, setLoadingProfile] = useState(false);

  // Load existing preferences from backend on mount (if authenticated)
  useEffect(() => {
    if (!authUserId || !isAuthenticated) return;
    let cancelled = false;
    setLoadingProfile(true);
    getUserProfile(authUserId)
      .then((profile) => {
        if (cancelled) return;
        if (profile.state_location) setStateLocation(profile.state_location);
        if (profile.allergies?.length) setSelectedAllergens(new Set(profile.allergies));
        if (profile.diet_preferences?.length) setSelectedDiets(new Set(profile.diet_preferences));
      })
      .catch(() => { /* first-time user — no profile yet */ })
      .finally(() => { if (!cancelled) setLoadingProfile(false); });
    return () => { cancelled = true; };
  }, [authUserId, isAuthenticated]);

  const toggleAllergen = (name: string) => {
    setSelectedAllergens((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  };

  const addCustomAllergen = () => {
    const trimmed = customAllergen.trim();
    if (!trimmed) return;
    setSelectedAllergens((prev) => new Set(prev).add(trimmed));
    setCustomAllergen('');
  };

  const toggleDiet = (name: string) => {
    setSelectedDiets((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  };

  const handleSave = async () => {
    setError('');
    if (!stateLocation) {
      setError('Please select your state.');
      return;
    }

    const prefs = {
      state_location: stateLocation,
      allergies: Array.from(selectedAllergens),
      diet_preferences: Array.from(selectedDiets),
    };

    if (authUserId && isAuthenticated) {
      setSaving(true);
      try {
        await updateUserPreferences(authUserId, prefs);
      } catch {
        setError('Could not save preferences to server. They are saved locally.');
      } finally {
        setSaving(false);
      }
    }

    // Always persist locally
    setUserPreferences(prefs);
    setHasCompletedProfile(true);
    navigate('/');
  };

  const handleSkip = () => {
    setHasCompletedProfile(true);
    navigate('/');
  };

  const sectionClass = 'border border-black/5 rounded-xl p-6 bg-white';
  const chipBase = 'px-4 py-2 rounded-full text-sm font-medium transition-colors cursor-pointer';
  const chipActive = 'bg-[#1A1A1A] text-white';
  const chipInactive = 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200';
  const inputClass =
    'flex-1 px-4 py-2.5 bg-cream border border-black/10 rounded-xl text-black placeholder-[#888] focus:outline-none focus:border-black/20';

  if (loadingProfile) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center text-[#888]">Loading profile...</div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-black">Set up your profile</h2>
        <p className="text-[#888] text-sm mt-1">
          Tell us where you are and what to watch out for so we can personalize your recall alerts and product scans.
        </p>
      </div>

      {/* ── State location ── */}
      <section className={sectionClass}>
        <div className="flex items-center gap-3 mb-4">
          <MapPin className="w-5 h-5 text-[#888]" />
          <h3 className="text-lg font-semibold text-black">Your state</h3>
        </div>
        <p className="text-[#888] text-sm mb-3">
          Food recalls are often limited to specific states. Select yours so we only show recalls distributed in your area.
        </p>
        <select
          value={stateLocation}
          onChange={(e) => setStateLocation(e.target.value)}
          className="w-full px-4 py-2.5 bg-cream border border-black/10 rounded-xl text-black focus:outline-none focus:border-black/20"
        >
          <option value="">Select your state...</option>
          {US_STATES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </section>

      {/* ── Allergies ── */}
      <section className={sectionClass}>
        <div className="flex items-center gap-3 mb-4">
          <AlertTriangle className="w-5 h-5 text-[#888]" />
          <h3 className="text-lg font-semibold text-black">Allergies</h3>
        </div>
        <p className="text-[#888] text-sm mb-3">
          Select allergens you need to avoid. When you scan or add a product to your cart, we will flag items that contain these ingredients.
        </p>
        <div className="flex flex-wrap gap-2 mb-4">
          {COMMON_ALLERGENS.map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => toggleAllergen(name)}
              className={`${chipBase} ${selectedAllergens.has(name) ? chipActive : chipInactive}`}
            >
              {name}
            </button>
          ))}
          {/* Show any custom allergens the user added */}
          {Array.from(selectedAllergens)
            .filter((a) => !COMMON_ALLERGENS.includes(a))
            .map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => toggleAllergen(name)}
                className={`${chipBase} ${chipActive}`}
              >
                {name}
              </button>
            ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={customAllergen}
            onChange={(e) => setCustomAllergen(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addCustomAllergen())}
            placeholder="Add a custom allergen..."
            className={inputClass}
          />
          <button
            type="button"
            onClick={addCustomAllergen}
            className="px-4 py-2.5 bg-neutral-100 text-black rounded-xl text-sm font-medium hover:bg-neutral-200"
          >
            Add
          </button>
        </div>
      </section>

      {/* ── Diet preferences ── */}
      <section className={sectionClass}>
        <div className="flex items-center gap-3 mb-4">
          <Leaf className="w-5 h-5 text-[#888]" />
          <h3 className="text-lg font-semibold text-black">Diet preferences</h3>
        </div>
        <p className="text-[#888] text-sm mb-3">
          Select any dietary restrictions. Products you scan will be checked against these preferences.
        </p>
        <div className="flex flex-wrap gap-2">
          {DIET_OPTIONS.map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => toggleDiet(name)}
              className={`${chipBase} ${selectedDiets.has(name) ? chipActive : chipInactive}`}
            >
              {name}
            </button>
          ))}
        </div>
      </section>

      {/* ── Actions ── */}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="flex gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="flex-1 py-3 rounded-xl text-sm font-medium text-white bg-[#1A1A1A] hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save & continue'}
        </button>
        <button
          type="button"
          onClick={handleSkip}
          className="px-6 py-3 rounded-xl text-sm font-medium text-[#888] border border-black/10 hover:text-[#1A1A1A] transition-colors"
        >
          Skip for now
        </button>
      </div>
      <p className="text-[#888] text-xs">
        You can update these anytime from Settings.
      </p>
    </div>
  );
}
