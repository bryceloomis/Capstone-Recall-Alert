/**
 * Shared TypeScript types for API requests/responses and UI.
 */
export interface Product {
  upc: string;
  product_name: string;
  brand_name: string;
  category?: string;
  ingredients?: string[];
  is_recalled: boolean;
  recall_info?: RecallInfo;
}

export interface RecallInfo {
  upc: string;
  product_name: string;
  brand_name: string;
  recall_date: string;
  reason: string;
  hazard_classification: 'Class I' | 'Class II' | 'Class III';
  firm_name: string;
  distribution: string;
}

export interface CartItem {
  upc: string;
  product_name: string;
  brand_name: string;
  added_date: string;
}

export interface UserCart {
  user_id: string;
  cart: CartItem[];
  count: number;
}

export interface SearchRequest {
  upc?: string;
  name?: string;
}

export interface SearchResponse {
  count?: number;
  results?: Product[];
  // Single product response
  upc?: string;
  product_name?: string;
  brand_name?: string;
  category?: string;
  ingredients?: string[];
  is_recalled?: boolean;
  recall_info?: RecallInfo;
}

/** User's ingredient preferences (ingredients to avoid). Not medical advice. */
export interface IngredientPreferences {
  ingredientsToAvoid: string[];
  customRestrictions: string[];
}

export interface UserProfile {
  userId: string;
  ingredientPreferences?: IngredientPreferences;
  notificationPreferences: {
    inApp: boolean;
    push: boolean;
    urgencyThreshold: 'all' | 'class1_only';
  };
}

/* ── Auth & user preferences (RDS-backed) ── */

export interface AuthRequest {
  username: string;
  password: string;
}

export interface AuthResponse {
  user_id: number;
  username: string;
  token: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
}

/** Persisted in the `user_preferences` RDS table. */
export interface UserPreferences {
  state_location: string;
  allergies: string[];
  diet_preferences: string[];
}

/** Full user row returned from GET /api/user/profile/:id */
export interface UserProfileFull {
  user_id: number;
  username: string;
  state_location: string | null;
  allergies: string[];
  diet_preferences: string[];
  created_at: string;
}
