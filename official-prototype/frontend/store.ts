/**
 * Global app state (Zustand, persisted to localStorage as "food-recall-storage").
 * Used for: userId, hasSeenOnboarding, cart, ingredientPreferences, userProfile.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { CartItem, UserProfile, IngredientPreferences } from './types';

interface AppState {
  userId: string;
  setUserId: (id: string) => void;
  
  cart: CartItem[];
  setCart: (cart: CartItem[]) => void;
  addToCart: (item: CartItem) => void;
  removeFromCart: (upc: string) => void;
  
  ingredientPreferences: IngredientPreferences | null;
  setIngredientPreferences: (profile: IngredientPreferences) => void;
  
  userProfile: UserProfile | null;
  setUserProfile: (profile: UserProfile) => void;
  
  hasSeenOnboarding: boolean;
  setHasSeenOnboarding: (seen: boolean) => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      userId: 'test_user',
      setUserId: (id) => set({ userId: id }),
      
      cart: [],
      setCart: (cart) => set({ cart }),
      addToCart: (item) => set((state) => ({
        cart: [...state.cart.filter(i => i.upc !== item.upc), item]
      })),
      removeFromCart: (upc) => set((state) => ({
        cart: state.cart.filter(i => i.upc !== upc)
      })),
      
      ingredientPreferences: null,
      setIngredientPreferences: (profile) => set({ ingredientPreferences: profile }),
      
      userProfile: null,
      setUserProfile: (profile) => set({ userProfile: profile }),
      
      hasSeenOnboarding: false,
      setHasSeenOnboarding: (seen) => set({ hasSeenOnboarding: seen }),
    }),
    {
      name: 'food-recall-storage',
    }
  )
);
