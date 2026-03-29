/**
 * React Query hooks for product search, risk scan, and cart.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { searchProduct, riskScan, getUserCart, addToCart, removeFromCart, getUserAlerts, dismissAlert } from './api';
import type { SearchRequest, CartItem, ScanResponse } from './types';
import { useStore } from './store';

export const useSearchProduct = () => {
  const userId = useStore((s) => s.userId);
  return useMutation({
    mutationFn: (request: SearchRequest) => searchProduct(request, userId),
  });
};

export const useRiskScan = () => {
  const userId = useStore((s) => s.userId);
  return useMutation({
    mutationFn: (upc: string): Promise<ScanResponse> => riskScan(upc, userId, true),
  });
};

export const useCart = (userId: string) => {
  return useQuery({
    queryKey: ['cart', userId],
    queryFn: () => getUserCart(userId),
    enabled: !!userId,
  });
};

export const useAddToCart = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (item: CartItem & { user_id: string }) => addToCart(item),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['cart', variables.user_id] });
    },
  });
};

export const useRemoveFromCart = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, upc }: { userId: string; upc: string }) =>
      removeFromCart(userId, upc),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['cart', variables.userId] });
    },
  });
};

export const useAlerts = (userId: string | number) => {
  return useQuery({
    queryKey: ['alerts', userId],
    queryFn: () => getUserAlerts(userId),
    enabled: !!userId,
  });
};

export const useDismissAlert = (userId: string | number) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alertId: number) => dismissAlert(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts', userId] });
    },
  });
};
