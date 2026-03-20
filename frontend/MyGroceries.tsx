/**
 * My Groceries: signed-in user's saved cart items.
 * Recall status comes from the pre-computed alerts table (written by the
 * background recall-refresh job) — no per-item scanning on page load.
 */
import { useMemo } from 'react';
import { ShoppingCart, Loader2, LogIn, Trash2, CheckCircle, ShieldX } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useCart, useRemoveFromCart, useAlerts } from './useProduct';
import { useStore } from './store';

export const MyGroceries = () => {
  const userId = useStore((s) => s.userId);
  const userProfile = useStore((s) => s.userProfile);
  const isSignedIn = userProfile != null && (userProfile.name != null || userProfile.email != null);

  const { data: cartData, isLoading: cartLoading } = useCart(userId);
  const { data: alertsData, isLoading: alertsLoading } = useAlerts(userId);
  const removeMutation = useRemoveFromCart();

  // Build a set of recalled product names from the alerts table (case-insensitive)
  const recalledNames = useMemo(() => {
    const s = new Set<string>();
    alertsData?.alerts?.forEach((a) => s.add(a.product_name.toLowerCase().trim()));
    return s;
  }, [alertsData]);

  // Build a map product_name → alert details for recalled items
  const alertByName = useMemo(() => {
    const m = new Map<string, typeof alertsData.alerts[0]>();
    alertsData?.alerts?.forEach((a) => m.set(a.product_name.toLowerCase().trim(), a));
    return m;
  }, [alertsData]);

  const handleRemove = async (upc: string) => {
    if (confirm('Remove this item from your list?')) {
      await removeMutation.mutateAsync({ userId, upc });
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
      });
    } catch { return dateStr; }
  };

  const isLoading = cartLoading || alertsLoading;

  return (
    <div className="max-w-4xl mx-auto space-y-8">
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

      {!isSignedIn && (
        <div className="rounded-xl p-5 border border-black/10 bg-black/[0.02] flex items-start gap-4">
          <LogIn className="w-5 h-5 text-[#888] shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-black">Sign in to see your grocery list</p>
            <p className="text-sm text-[#888] mt-1">Create an account to save products and get recall alerts.</p>
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

      {isSignedIn && (
        <>
          {isLoading && (
            <div className="flex justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-[#888]" />
            </div>
          )}

          {!isLoading && cartData && cartData.cart.length === 0 && (
            <div className="rounded-xl p-10 border border-black/10 text-center">
              <ShoppingCart className="w-10 h-10 text-black/20 mx-auto mb-3" />
              <p className="text-sm font-medium text-black">Your grocery list is empty</p>
              <p className="text-xs text-[#888] mt-1">Scan a product or search on Home to add items.</p>
            </div>
          )}

          {!isLoading && cartData && cartData.cart.length > 0 && (
            <div className="space-y-3">
              {cartData.cart.map((item) => {
                const key = item.product_name.toLowerCase().trim();
                const isRecalled = recalledNames.has(key);
                const alert = alertByName.get(key);

                return (
                  <div
                    key={item.upc ?? item.product_name}
                    className={`rounded-xl border p-4 bg-white transition-colors ${
                      isRecalled ? 'border-red-200' : 'border-black/5'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-medium text-black">{item.product_name}</h3>
                          {isRecalled ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs font-medium">
                              <ShieldX className="w-3 h-3" /> Recalled
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full text-xs font-medium">
                              <CheckCircle className="w-3 h-3" /> Safe
                            </span>
                          )}
                        </div>

                        {item.brand_name && (
                          <p className="text-sm text-[#888] mt-0.5">{item.brand_name}</p>
                        )}

                        <p className="text-xs text-[#888] mt-2">Added {formatDate(item.added_date)}</p>
                      </div>

                      <button
                        onClick={() => handleRemove(item.upc)}
                        disabled={removeMutation.isPending}
                        className="p-2 text-[#888] hover:text-red-500 transition-colors rounded-lg hover:bg-red-50 shrink-0"
                        aria-label="Remove item"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    {isRecalled && alert && (
                      <div className="mt-3 pt-3 border-t border-red-100 space-y-1">
                        <p className="text-xs text-red-700">
                          <span className="font-medium">Reason:</span> {alert.recall.reason}
                        </p>
                        {alert.recall.severity && (
                          <p className="text-xs text-red-700">
                            <span className="font-medium">Class:</span> {alert.recall.severity}
                          </p>
                        )}
                        {alert.recall.recall_date && (
                          <p className="text-xs text-red-700">
                            <span className="font-medium">Date:</span> {formatDate(String(alert.recall.recall_date))}
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

      <div className="pt-4 border-t border-black/10 text-center">
        <Link to="/groceries-example" className="text-xs text-[#888] hover:text-black transition-colors">
          View demo example →
        </Link>
      </div>
    </div>
  );
};
