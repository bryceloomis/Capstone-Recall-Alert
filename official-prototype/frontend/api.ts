/**
 * API layer: all HTTP calls to the FastAPI backend.
 * - searchProduct / checkRecallByUPC: product lookup (backend then Open Food Facts fallback).
 * - Cart: getUserCart, addToCart, removeFromCart.
 * - getFdaRecalls: optional FDA recall endpoint (see backend/fda_recalls.py).
 */
import axios from 'axios';
import type { Product, SearchRequest, SearchResponse, UserCart, CartItem, RecallInfo } from './types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

/** Map backend recall payload to app RecallInfo (e.g. hazard class string → Class I/II/III). */
function mapRecallInfo(raw: Record<string, unknown> | null | undefined): RecallInfo | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const classification = mapToHazardClass(raw);
  return {
    upc: String(raw.upc ?? ''),
    product_name: String(raw.product_name ?? ''),
    brand_name: String(raw.brand_name ?? ''),
    recall_date: String(raw.recall_date ?? ''),
    reason: String(raw.reason ?? ''),
    hazard_classification: classification,
    firm_name: String(raw.firm_name ?? ''),
    distribution: String(raw.distribution ?? ''),
  };
}

function mapToHazardClass(raw: Record<string, unknown>): 'Class I' | 'Class II' | 'Class III' {
  const v = (raw.hazard_classification ?? raw.hazard_class ?? raw.classification ?? raw.class ?? '') as string;
  const lower = String(v).toLowerCase();
  if (lower.includes('i') && !lower.includes('ii') && !lower.includes('iii')) return 'Class I';
  if (lower.includes('iii')) return 'Class III';
  if (lower.includes('ii')) return 'Class II';
  return 'Class II';
}

/**
 * Check recall by UPC: try FastAPI backend first; if product not in DB, fall back to Open Food Facts.
 */
export async function checkRecallByUPC(upc: string): Promise<Product> {
  try {
    const res = await fetch(`${API_BASE}/api/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ upc }),
    });

    if (!res.ok) {
      return checkOpenFoodFacts(upc);
    }

    const data = (await res.json()) as Record<string, unknown>;
    const recallInfo = data.recall_info != null ? mapRecallInfo(data.recall_info as Record<string, unknown>) : undefined;
    return {
      upc: String(data.upc ?? upc),
      product_name: String(data.product_name ?? 'Unknown'),
      brand_name: String(data.brand_name ?? ''),
      category: data.category as string | undefined,
      ingredients: Array.isArray(data.ingredients) ? (data.ingredients as string[]) : undefined,
      is_recalled: Boolean(data.is_recalled),
      recall_info: recallInfo,
    };
  } catch {
    return checkOpenFoodFacts(upc);
  }
}

/**
 * Fallback when UPC is not in local DB: fetch from Open Food Facts (no recall cross-check here).
 */
export async function checkOpenFoodFacts(upc: string): Promise<Product> {
  const res = await fetch(`https://world.openfoodfacts.org/api/v2/product/${upc}.json`);
  const data = await res.json();

  if (data.status === 0 || !data.product) {
    return {
      upc,
      product_name: `Product ${upc}`,
      brand_name: 'Unknown',
      is_recalled: false,
    };
  }

  const product = data.product as Record<string, unknown>;
  const ingredientsTags = product.ingredients_tags as string[] | undefined;
  const ingredients = Array.isArray(ingredientsTags)
    ? ingredientsTags.map((t: string) => t.replace(/^[a-z]{2}:/, ''))
    : undefined;

  return {
    upc,
    product_name: (product.product_name as string) || 'Unknown Product',
    brand_name: (product.brands as string) || 'Unknown Brand',
    category: product.categories as string | undefined,
    ingredients,
    is_recalled: false,
  };
}

export const healthCheck = async () => {
  const { data } = await api.get('/api/health');
  return data;
};

export const searchProduct = async (request: SearchRequest): Promise<Product | Product[]> => {
  // UPC-only search: use backend + Open Food Facts fallback
  if (request.upc != null && request.upc !== '' && request.name == null) {
    return checkRecallByUPC(request.upc);
  }

  const { data } = await api.post<SearchResponse>('/api/search', request);

  // Handle single product response
  if (data.upc && data.product_name) {
    const recallInfo = data.recall_info != null ? mapRecallInfo(data.recall_info as unknown as Record<string, unknown>) : data.recall_info;
    return {
      upc: data.upc,
      product_name: data.product_name,
      brand_name: data.brand_name || '',
      category: data.category,
      ingredients: data.ingredients,
      is_recalled: data.is_recalled ?? false,
      recall_info: recallInfo,
    };
  }

  // Handle multiple products response
  if (data.results) {
    return data.results;
  }

  throw new Error('Invalid response format');
};

export const getAllRecalls = async () => {
  const { data } = await api.get('/api/recalls');
  return data;
};

/**
 * Query FDA recalls via your backend (server-side call to openFDA).
 * Use once you add GET /api/recalls/fda to app.py (see backend/fda_recalls.py).
 */
export const getFdaRecalls = async (params: { upc?: string; product_name?: string }) => {
  const { data } = await api.get<{ results?: unknown[] }>('/api/recalls/fda', { params });
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

export default api;
