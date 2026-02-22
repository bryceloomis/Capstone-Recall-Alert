/**
 * Global app state (Zustand, persisted to localStorage as "food-recall-storage").
 * Used for: auth, userId, hasSeenOnboarding, cart, ingredientPreferences, userProfile, userPreferences.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { CartItem, UserProfile, IngredientPreferences, UserPreferences } from './types';
import { setAuthToken } from './api';

interface AppState {
  /* ── Auth ── */
  isAuthenticated: boolean;
  authToken: string | null;
  authUserId: number | null;       // numeric id from RDS `users` table
  authUsername: string | null;
  login: (token: string, userId: number, username: string) => void;
  logout: () => void;

  /* ── Profile setup completed flag ── */
  hasCompletedProfile: boolean;
  setHasCompletedProfile: (done: boolean) => void;

  /* ── User preferences (state, allergies, diet) from RDS ── */
  userPreferences: UserPreferences | null;
  setUserPreferences: (prefs: UserPreferences) => void;

  /* ── Legacy user id (string, used by cart API) ── */
  userId: string;
  setUserId: (id: string) => void;

  /* ── Cart ── */
  cart: CartItem[];
  setCart: (cart: CartItem[]) => void;
  addToCart: (item: CartItem) => void;
  removeFromCart: (upc: string) => void;

  /* ── Ingredient preferences (V2 feature) ── */
  ingredientPreferences: IngredientPreferences | null;
  setIngredientPreferences: (profile: IngredientPreferences) => void;

  /* ── User profile (legacy) ── */
  userProfile: UserProfile | null;
  setUserProfile: (profile: UserProfile) => void;

  /* ── Onboarding ── */
  hasSeenOnboarding: boolean;
  setHasSeenOnboarding: (seen: boolean) => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      /* ── Auth ── */
      isAuthenticated: false,
      authToken: null,
      authUserId: null,
      authUsername: null,
      login: (token, userId, username) => {
        setAuthToken(token);
        set({
          isAuthenticated: true,
          authToken: token,
          authUserId: userId,
          authUsername: username,
          userId: String(userId),
          hasSeenOnboarding: true,
        });
      },
      logout: () => {
        setAuthToken(null);
        set({
          isAuthenticated: false,
          authToken: null,
          authUserId: null,
          authUsername: null,
          hasCompletedProfile: false,
          userPreferences: null,
          hasSeenOnboarding: false,
          cart: [],
        });
      },

      /* ── Profile setup ── */
      hasCompletedProfile: false,
      setHasCompletedProfile: (done) => set({ hasCompletedProfile: done }),

      /* ── User preferences ── */
      userPreferences: null,
      setUserPreferences: (prefs) => set({ userPreferences: prefs }),

      /* ── Legacy userId ── */
      userId: 'test_user',
      setUserId: (id) => set({ userId: id }),

      /* ── Cart ── */
      cart: [],
      setCart: (cart) => set({ cart }),
      addToCart: (item) => set((state) => ({
        cart: [...state.cart.filter(i => i.upc !== item.upc), item]
      })),
      removeFromCart: (upc) => set((state) => ({
        cart: state.cart.filter(i => i.upc !== upc)
      })),

      /* ── Ingredient preferences ── */
      ingredientPreferences: null,
      setIngredientPreferences: (profile) => set({ ingredientPreferences: profile }),

      /* ── User profile (legacy) ── */
      userProfile: null,
      setUserProfile: (profile) => set({ userProfile: profile }),

      /* ── Onboarding ── */
      hasSeenOnboarding: false,
      setHasSeenOnboarding: (seen) => set({ hasSeenOnboarding: seen }),
    }),
    {
      name: 'food-recall-storage',
      onRehydrate: () => {
        // Re-attach the auth token to axios after page reload
        return (state) => {
          if (state?.authToken) {
            setAuthToken(state.authToken);
          }
        };
      },
    }
  )
);
