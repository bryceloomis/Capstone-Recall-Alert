/**
 * Shared TypeScript types matching the backend API response shapes
 * from the ingredient_diet_workflow branch.
 */

export type Verdict = 'OK' | 'CAUTION' | 'DONT_BUY';

export interface RecallSummary {
  headline: string;
  what_happened: string;
  what_to_do: string;
  who_is_at_risk: string;
  severity_plain: string;
}

export interface RecallInfo {
  id?: number;
  upc: string;
  product_name: string;
  brand_name: string;
  recall_date: string;
  reason: string;
  hazard_classification: 'Class I' | 'Class II' | 'Class III';
  source?: string;
  firm_name: string;
  distribution: string;
  match_method?: string;
  match_confidence?: number;
  summary?: RecallSummary;
}

export interface RiskNotification {
  type: 'RECALL' | 'ALLERGEN' | 'DIET' | 'ADDITIVE' | 'WARNING';
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  title: string;
  message: string;
}

export interface AllergenMatch {
  allergen: string;
  matched_token: string;
  confidence: 'DEFINITE' | 'PROBABLE' | 'POSSIBLE';
  severity: 'HIGH' | 'MEDIUM';
  is_advisory: boolean;
}

export interface DietFlag {
  diet: string;
  flagged_token: string;
  reason: string;
  confidence: 'DEFINITE' | 'PROBABLE' | 'POSSIBLE';
}

export interface HardStop {
  gate: string;
  reason: string;
}

export interface CautionSignal {
  category: string;
  detail: string;
  points: number;
}

export interface RiskReport {
  verdict: Verdict;
  explanation: string[];
  is_recalled: boolean;
  hard_stops: HardStop[];
  caution_signals: CautionSignal[];
  allergen_count: number;
  allergen_matches: AllergenMatch[];
  diet_flag_count: number;
  diet_flags: DietFlag[];
  parsed_ingredients: string[];
  _caution_score: number;
}

export interface ProductInfo {
  upc: string;
  product_name: string;
  brand_name: string;
  category?: string;
  ingredients?: string[];
  image_url?: string;
}

/** Full response from GET /api/risk/scan/{upc} */
export interface ScanResponse {
  found: boolean;
  product?: ProductInfo;
  recall?: RecallInfo | null;
  verdict?: Verdict | null;
  explanation?: string[];
  notifications?: RiskNotification[];
  risk?: RiskReport | null;
  upc?: string;
  message?: string;
}

/** Legacy Product shape for backward compat with search/cart */
export interface Product {
  upc: string;
  product_name: string;
  brand_name: string;
  category?: string;
  ingredients?: string[];
  image_url?: string;
  is_recalled: boolean;
  recall_info?: RecallInfo;
  verdict?: Verdict;
  notifications?: RiskNotification[];
  risk?: RiskReport;
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
  upc?: string;
  product_name?: string;
  brand_name?: string;
  category?: string;
  ingredients?: string[];
  is_recalled?: boolean;
  recall_info?: RecallInfo;
  found?: boolean;
  verdict?: Verdict;
  explanation?: string[];
  risk?: RiskReport;
}

export interface IngredientPreferences {
  ingredientsToAvoid: string[];
  customRestrictions: string[];
}

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  state?: string;
  allergens?: string[];
  diet_preferences?: string[];
  created_at: string;
}

export interface UserProfile {
  id?: number;
  name?: string;
  email?: string;
  state?: string;
  allergens?: string[];
  diet_preferences?: string[];
  userId?: string;
  ingredientPreferences?: IngredientPreferences;
  notificationPreferences?: {
    inApp: boolean;
    push: boolean;
    urgencyThreshold: 'all' | 'class1_only';
  };
}

export interface ReceiptMatchedProduct {
  raw_text: string;
  cleaned_text: string;
  upc: string;
  product_name: string;
  brand_name: string;
  ingredients: string[];
  is_recalled: boolean;
  recall_info?: RecallInfo;
  source?: string;
}

export interface ReceiptScanResult {
  matched: ReceiptMatchedProduct[];
  unmatched: string[];
  total_lines: number;
}

export const COMMON_ALLERGENS = [
  'Milk', 'Eggs', 'Fish', 'Shellfish', 'Tree nuts',
  'Peanuts', 'Wheat', 'Soybeans', 'Sesame',
] as const;

export const COMMON_DIETS = [
  'Vegan', 'Vegetarian', 'Gluten-free', 'Keto',
  'Paleo', 'Halal', 'Kosher', 'Dairy-free',
] as const;

export const US_STATES = [
  'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
  'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
  'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
  'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
  'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC',
] as const;
