/**
 * React Query hooks for product search and cart (backend API).
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { searchProduct, getUserCart, addToCart, removeFromCart } from './api';
import type { SearchRequest, CartItem } from './types';

export const useSearchProduct = () => {
  return useMutation({
    mutationFn: (request: SearchRequest) => searchProduct(request),
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
