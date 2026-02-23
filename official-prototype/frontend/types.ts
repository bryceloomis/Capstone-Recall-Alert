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
  /** Set after registration/login */
  name?: string;
  email?: string;
  /** Legacy field used before auth was added */
  userId?: string;
  ingredientPreferences?: IngredientPreferences;
  notificationPreferences?: {
    inApp: boolean;
    push: boolean;
    urgencyThreshold: 'all' | 'class1_only';
  };
}
