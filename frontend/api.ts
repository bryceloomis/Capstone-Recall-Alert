/**
 * API layer: all HTTP calls to the FastAPI backend.
 * Primary scan uses GET /api/risk/scan/{upc} from the ingredient_diet_workflow branch.
 */
import axios from 'axios';
import type {
  Product, SearchRequest, SearchResponse, UserCart, CartItem,
  RecallInfo, ScanResponse, AuthUser, ReceiptScanResult, ReceiptMatchedProduct, ReceiptSafeItem,
} from './types';

export type { ReceiptScanResult, ReceiptMatchedProduct, ReceiptSafeItem };

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

function mapToHazardClass(raw: Record<string, unknown>): 'Class I' | 'Class II' | 'Class III' {
  const v = (raw.hazard_classification ?? raw.hazard_class ?? raw.classification ?? '') as string;
  const lower = String(v).toLowerCase();
  if (lower.includes('iii')) return 'Class III';
  if (lower.includes('ii')) return 'Class II';
  if (lower.includes('i')) return 'Class I';
  return 'Class II';
}

function mapRecallInfo(raw: Record<string, unknown> | null | undefined): RecallInfo | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  return {
    id: raw.id as number | undefined,
    upc: String(raw.upc ?? ''),
    product_name: String(raw.product_name ?? ''),
    brand_name: String(raw.brand_name ?? ''),
    recall_date: String(raw.recall_date ?? ''),
    reason: String(raw.reason ?? ''),
    hazard_classification: mapToHazardClass(raw),
    source: raw.source as string | undefined,
    firm_name: String(raw.firm_name ?? ''),
    distribution: String(raw.distribution ?? ''),
    match_method: raw.match_method as string | undefined,
    match_confidence: raw.match_confidence as number | undefined,
    summary: raw.summary as RecallInfo['summary'],
  };
}

/**
 * Primary scan endpoint. Calls GET /api/risk/scan/{upc}.
 * Returns full risk analysis including verdict, notifications, allergen matches, diet flags.
 */
export async function riskScan(upc: string, userId?: string | number, enableAi = false): Promise<ScanResponse> {
  const params = new URLSearchParams();
  if (userId != null) params.set('user_id', String(userId));
  if (enableAi) params.set('enable_ai', 'true');

  const url = `${API_BASE}/api/risk/scan/${encodeURIComponent(upc)}${params.toString() ? '?' + params.toString() : ''}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Scan failed (${res.status})`);
  }
  return res.json() as Promise<ScanResponse>;
}

/** Convert ScanResponse to a Product for backward compat with components that use Product. */
export function scanResponseToProduct(scan: ScanResponse): Product {
  if (!scan.found || !scan.product) {
    return {
      upc: scan.upc ?? '',
      product_name: 'Product not found',
      brand_name: '',
      is_recalled: false,
    };
  }
  return {
    upc: scan.product.upc,
    product_name: scan.product.product_name,
    brand_name: scan.product.brand_name,
    category: scan.product.category,
    ingredients: scan.product.ingredients,
    image_url: scan.product.image_url,
    is_recalled: scan.risk?.is_recalled ?? scan.recall != null,
    recall_info: scan.recall ? mapRecallInfo(scan.recall as unknown as Record<string, unknown>) : undefined,
    verdict: scan.verdict ?? undefined,
    notifications: scan.notifications,
    risk: scan.risk ?? undefined,
  };
}

/** Fallback: Open Food Facts lookup. */
export async function checkOpenFoodFacts(upc: string): Promise<Product> {
  const res = await fetch(`https://world.openfoodfacts.org/api/v2/product/${upc}.json`);
  const data = await res.json();
  if (data.status === 0 || !data.product) {
    return { upc, product_name: `Product ${upc}`, brand_name: 'Unknown', is_recalled: false };
  }
  const p = data.product as Record<string, unknown>;
  const tags = p.ingredients_tags as string[] | undefined;
  const ingredients = Array.isArray(tags) ? tags.map((t: string) => t.replace(/^[a-z]{2}:/, '')) : undefined;
  return {
    upc,
    product_name: (p.product_name as string) || 'Unknown Product',
    brand_name: (p.brands as string) || 'Unknown Brand',
    category: p.categories as string | undefined,
    ingredients,
    image_url: (p.image_front_small_url as string) || (p.image_url as string) || undefined,
    is_recalled: false,
  };
}

/**
 * Combined lookup: tries risk scan, falls back to Open Food Facts.
 */
export async function lookupByUPC(upc: string, userId?: string | number): Promise<{ product: Product; scan: ScanResponse | null }> {
  try {
    const scan = await riskScan(upc, userId, true);
    return { product: scanResponseToProduct(scan), scan };
  } catch {
    const product = await checkOpenFoodFacts(upc);
    return { product, scan: null };
  }
}

export const healthCheck = async () => {
  const { data } = await api.get('/api/health');
  return data;
};

export const searchProduct = async (request: SearchRequest, userId?: string | number): Promise<Product | Product[]> => {
  if (request.upc && !request.name) {
    const { product } = await lookupByUPC(request.upc, userId);
    return product;
  }
  const { data } = await api.post<SearchResponse>('/api/search', { ...request, user_id: userId ? Number(userId) : undefined });
  if (data.upc && data.product_name) {
    return {
      upc: data.upc,
      product_name: data.product_name,
      brand_name: data.brand_name || '',
      category: data.category,
      ingredients: data.ingredients,
      is_recalled: data.is_recalled ?? false,
      recall_info: data.recall_info ? mapRecallInfo(data.recall_info as unknown as Record<string, unknown>) : undefined,
      verdict: data.verdict,
      risk: data.risk ?? undefined,
    };
  }
  if (data.results) return data.results;
  throw new Error('Invalid response format');
};

export const getAllRecalls = async () => {
  const { data } = await api.get('/api/recalls');
  return data;
};

export const getUserCart = async (userId: string): Promise<UserCart> => {
  const { data } = await api.get<UserCart>(`/api/user/cart/${userId}`);
  return data;
};

export const addToCart = async (item: CartItem & { user_id: string }) => {
  const { data } = await api.post('/api/user/cart', item);
  return data;
};

export const removeFromCart = async (userId: string, upc: string) => {
  const { data } = await api.delete(`/api/user/cart/${userId}/${upc}`);
  return data;
};

export async function scanReceipt(file: File, userId?: string): Promise<ReceiptScanResult> {
  const formData = new FormData();
  formData.append('file', file);
  if (userId) formData.append('user_id', userId);
  const res = await fetch(`${API_BASE}/api/receipt/scan`, { method: 'POST', body: formData });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error((err as { detail?: string }).detail ?? 'Receipt scan failed');
  }
  return res.json() as Promise<ReceiptScanResult>;
}

/** Register with allergens and diet preferences. */
export const registerUser = async (
  name: string, email: string, password: string,
  allergens: string[] = [], dietPreferences: string[] = [], state?: string
): Promise<AuthUser> => {
  const { data } = await api.post<{ message: string; user: AuthUser }>('/api/users/register', {
    name, email, password, state, allergens, diet_preferences: dietPreferences,
  });
  return data.user;
};

export const loginUser = async (email: string, password: string): Promise<AuthUser> => {
  const { data } = await api.post<{ message: string; user: AuthUser }>('/api/users/login', { email, password });
  return data.user;
};

/** Fetch the user's allergen/diet profile. */
export const getUserProfile = async (userId: number | string): Promise<AuthUser> => {
  const { data } = await api.get<AuthUser>(`/api/users/${userId}/profile`);
  return data;
};

/** Update allergens, diets, or state. */
export const updateUserProfile = async (
  userId: number | string,
  updates: { allergens?: string[]; diet_preferences?: string[]; state?: string }
): Promise<AuthUser> => {
  const { data } = await api.patch<{ message: string; user: AuthUser }>(`/api/users/${userId}/profile`, updates);
  return data.user;
};

/** Get recall alerts for a user. */
export const getUserAlerts = async (userId: string | number) => {
  const { data } = await api.get<{
    user_id: string;
    alerts: Array<{
      alert_id: number;
      product_upc: string;
      product_name: string;
      viewed: boolean;
      created_at: string;
      recall: RecallInfo;
    }>;
    count: number;
    unviewed_count: number;
  }>(`/api/alerts/${userId}`);
  return data;
};

/** Mark an alert as viewed. */
export const markAlertViewed = async (alertId: number) => {
  const { data } = await api.patch(`/api/alerts/${alertId}/viewed`);
  return data;
};

/** Dismiss an alert — user says "that's not my product". */
export const dismissAlert = async (alertId: number) => {
  const { data } = await api.patch(`/api/alerts/${alertId}/dismiss`);
  return data;
};

export default api;
