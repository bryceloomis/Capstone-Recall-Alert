/**
 * My Groceries: shows the signed-in user's actual saved cart items from the API.
 * Displays: product name, brand, ingredients (fetched from Open Food Facts), date added, recall status.
 */
import { useState, useEffect } from 'react';
import { ShoppingCart, Loader2, LogIn, Trash2, AlertCircle, CheckCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useCart, useRemoveFromCart } from './useProduct';
import { lookupByUPC } from './api';
import { useStore } from './store';
import type { Product } from './types';

export const MyGroceries = () => {
  const userId      = useStore((state) => state.userId);
  const userProfile = useStore((state) => state.userProfile);
  const isSignedIn  = userProfile != null && (userProfile.name != null || userProfile.email != null);

  const { data: cartData, isLoading } = useCart(userId);
  const removeMutation = useRemoveFromCart();

  /** Enriched product details (ingredients, recall status) keyed by UPC. */
  const [productDetails, setProductDetails] = useState<Record<string, Product>>({});
  const [loadingDetails, setLoadingDetails] = useState(false);

  // When cart loads, fetch full product info (including ingredients) for each item in parallel.
  useEffect(() => {
    if (!cartData?.cart?.length) return;
    setLoadingDetails(true);
    Promise.allSettled(
      cartData.cart.map((item) =>
        lookupByUPC(item.upc).then((p) => ({ upc: item.upc, product: p }))
      )
    )
      .then((results) => {
        const details: Record<string, Product> = {};
        results.forEach((r) => {
          if (r.status === 'fulfilled') {
            details[r.value.upc] = r.value.product;
          }
        });
        setProductDetails(details);
      })
      .finally(() => setLoadingDetails(false));
  }, [cartData?.cart?.length]);

  const handleRemove = async (upc: string) => {
    if (confirm('Remove this item from your list?')) {
      await removeMutation.mutateAsync({ userId, upc });
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShoppingCart className="w-7 h-7 text-black" />
          <h2 className="text-xl font-semibold text-black">My Groceries</h2>
        </div>
        {isSignedIn && cartData && (
          <span className="px-3 py-1.5 bg-black/5 text-[#888] rounded-full text-sm font-medium">
            {cartData.count} {cartData.count === 1 ? 'item' : 'items'}
          </span>
        )}
      </div>

      {/* Guest: sign-in prompt */}
      {!isSignedIn && (
        <div className="rounded-xl p-5 border border-black/10 bg-black/[0.02] flex items-start gap-4">
          <LogIn className="w-5 h-5 text-[#888] shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-black">Sign in to see your grocery list</p>
            <p className="text-sm text-[#888] mt-1">
              Create an account to save products across devices and get recall alerts.
            </p>
            <Link
              to="/"
              onClick={() => useStore.getState().setHasSeenOnboarding(false)}
              className="inline-block mt-3 px-4 py-2 bg-black text-white text-sm font-medium rounded-xl hover:opacity-90 transition-opacity"
            >
              Sign in or create account
            </Link>
          </div>
        </div>
      )}

      {/* Signed in: cart */}
      {isSignedIn && (
        <>
          {/* Loading cart */}
          {isLoading && (
            <div className="flex justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-[#888]" />
            </div>
          )}

          {/* Empty cart */}
          {!isLoading && cartData && cartData.cart.length === 0 && (
            <div className="rounded-xl p-10 border border-black/10 text-center">
              <ShoppingCart className="w-10 h-10 text-black/20 mx-auto mb-3" />
              <p className="text-sm font-medium text-black">Your grocery list is empty</p>
              <p className="text-xs text-[#888] mt-1">Scan a product barcode or search on Home to add items.</p>
            </div>
          )}

          {/* Cart items */}
          {!isLoading && cartData && cartData.cart.length > 0 && (
            <div className="space-y-3">
              {loadingDetails && (
                <p className="text-xs text-[#888] flex items-center gap-2">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Loading product details…
                </p>
              )}
              {cartData.cart.map((item) => {
                const details = productDetails[item.upc];
                const isRecalled = details?.is_recalled ?? false;
                const ingredients = details?.ingredients;

                return (
                  <div
                    key={item.upc}
                    className={`rounded-xl border p-4 bg-white transition-colors ${
                      isRecalled ? 'border-red-200' : 'border-black/5'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        {/* Name + recall badge */}
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-medium text-black">{item.product_name}</h3>
                          {details && (
                            isRecalled ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs font-medium">
                                <AlertCircle className="w-3 h-3" />
                                Recalled
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full text-xs font-medium">
                                <CheckCircle className="w-3 h-3" />
                                No recall
                              </span>
                            )
                          )}
                        </div>

                        {/* Brand */}
                        <p className="text-sm text-[#888] mt-0.5">{item.brand_name}</p>

                        {/* Ingredients */}
                        {ingredients && ingredients.length > 0 && (
                          <p className="text-xs text-[#888] mt-2 leading-relaxed">
                            <span className="font-medium text-black">Ingredients: </span>
                            {ingredients.join(', ')}
                          </p>
                        )}

                        {/* Date added */}
                        <p className="text-xs text-[#888] mt-2">
                          Added {formatDate(item.added_date)}
                        </p>
                      </div>

                      {/* Remove button */}
                      <button
                        onClick={() => handleRemove(item.upc)}
                        disabled={removeMutation.isPending}
                        className="p-2 text-[#888] hover:text-red-500 transition-colors rounded-lg hover:bg-red-50 shrink-0"
                        aria-label="Remove item"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Recall details */}
                    {isRecalled && details?.recall_info && (
                      <div className="mt-3 pt-3 border-t border-red-100 space-y-1">
                        <p className="text-xs text-red-700">
                          <span className="font-medium">Reason: </span>
                          {details.recall_info.reason}
                        </p>
                        <p className="text-xs text-red-700">
                          <span className="font-medium">Class: </span>
                          {details.recall_info.hazard_classification}
                        </p>
                        {details.recall_info.recall_date && (
                          <p className="text-xs text-red-700">
                            <span className="font-medium">Date: </span>
                            {details.recall_info.recall_date}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Footer: link to example page */}
      <div className="pt-4 border-t border-black/10 text-center">
        <Link
          to="/groceries-example"
          className="text-xs text-[#888] hover:text-black transition-colors"
        >
          View demo example →
        </Link>
      </div>
    </div>
  );
};
