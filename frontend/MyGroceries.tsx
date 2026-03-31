/**
 * My Groceries: signed-in user's saved cart items with risk data per item.
 * Uses risk scan endpoint for each item to show verdict, allergens, diet flags.
 */
import { useState, useEffect } from 'react';
import { ShoppingCart, Loader2, LogIn, Trash2, AlertCircle, CheckCircle, ShieldAlert, ShieldX } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useCart, useRemoveFromCart } from './useProduct';
import { riskScan, scanResponseToProduct } from './api';
import { useStore } from './store';
import type { Product, ScanResponse } from './types';

export const MyGroceries = () => {
  const userId = useStore((s) => s.userId);
  const userProfile = useStore((s) => s.userProfile);
  const isSignedIn = userProfile != null && (userProfile.name != null || userProfile.email != null);

  const { data: cartData, isLoading } = useCart(userId);
  const removeMutation = useRemoveFromCart();

  const [productDetails, setProductDetails] = useState<Record<string, { product: Product; scan: ScanResponse | null }>>({});
  const [loadingDetails, setLoadingDetails] = useState(false);

  useEffect(() => {
    if (!cartData?.cart?.length) return;
    setLoadingDetails(true);
    Promise.allSettled(
      cartData.cart.map(async (item) => {
        try {
          const scan = await riskScan(item.upc, userId, true);
          return { upc: item.upc, product: scanResponseToProduct(scan), scan };
        } catch {
          return { upc: item.upc, product: { upc: item.upc, product_name: item.product_name, brand_name: item.brand_name, is_recalled: false } as Product, scan: null };
        }
      })
    ).then((results) => {
      const details: Record<string, { product: Product; scan: ScanResponse | null }> = {};
      results.forEach((r) => {
        if (r.status === 'fulfilled') details[r.value.upc] = r.value;
      });
      setProductDetails(details);
    }).finally(() => setLoadingDetails(false));
  }, [cartData?.cart?.length, userId]);

  const handleRemove = async (upc: string) => {
    if (confirm('Remove this item from your list?')) {
      await removeMutation.mutateAsync({ userId, upc });
    }
  };

  const formatDate = (dateStr: string) => {
    try { return new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }); }
    catch { return dateStr; }
  };

  const VerdictBadge = ({ verdict, isRecalled }: { verdict?: string | null; isRecalled: boolean }) => {
    if (verdict === 'DONT_BUY' || isRecalled) {
      return <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs font-medium"><ShieldX className="w-3 h-3" />{isRecalled ? 'Recalled' : "Don't buy"}</span>;
    }
    if (verdict === 'CAUTION') {
      return <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs font-medium"><ShieldAlert className="w-3 h-3" />Caution</span>;
    }
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full text-xs font-medium"><CheckCircle className="w-3 h-3" />Safe</span>;
  };

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
            <Link to="/" onClick={() => useStore.getState().setHasSeenOnboarding(false)}
              className="inline-block mt-3 px-4 py-2 bg-black text-white text-sm font-medium rounded-xl hover:opacity-90 transition-opacity">
              Sign in or create account
            </Link>
          </div>
        </div>
      )}

      {isSignedIn && (
        <>
          {isLoading && (
            <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-[#888]" /></div>
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
              {loadingDetails && (
                <p className="text-xs text-[#888] flex items-center gap-2">
                  <Loader2 className="w-3 h-3 animate-spin" /> Running risk analysis…
                </p>
              )}
              {cartData.cart.map((item) => {
                const detail = productDetails[item.upc];
                const product = detail?.product;
                const scan = detail?.scan;
                const isRecalled = product?.is_recalled ?? false;
                const verdict = product?.verdict ?? scan?.verdict;
                const notifications = scan?.notifications ?? [];

                return (
                  <div key={item.upc}
                    className={`rounded-xl border p-4 bg-white transition-colors ${
                      verdict === 'DONT_BUY' || isRecalled ? 'border-red-200' :
                      verdict === 'CAUTION' ? 'border-amber-200' : 'border-black/5'
                    }`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-medium text-black">{item.product_name}</h3>
                          {product && <VerdictBadge verdict={verdict} isRecalled={isRecalled} />}
                        </div>
                        <p className="text-sm text-[#888] mt-0.5">{item.brand_name}</p>

                        {/* Notifications */}
                        {notifications.length > 0 && (
                          <div className="mt-2 space-y-1">
                            {notifications.slice(0, 3).map((n, i) => (
                              <div key={i} className={`text-xs px-2 py-1.5 rounded ${
                                n.severity === 'HIGH' ? 'bg-red-50 text-red-700' :
                                n.severity === 'MEDIUM' ? 'bg-amber-50 text-amber-700' :
                                'bg-black/[0.02] text-[#555]'
                              }`}>
                                <span className="font-semibold">{n.title}: </span>
                                {n.summary || n.message}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Allergen matches */}
                        {scan?.risk?.allergen_matches && scan.risk.allergen_matches.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {scan.risk.allergen_matches.map((m, i) => (
                              <span key={i} className="text-[10px] px-2 py-0.5 bg-red-50 text-red-700 rounded-full border border-red-100 font-medium">
                                {m.allergen}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Diet flags */}
                        {scan?.risk?.diet_flags && scan.risk.diet_flags.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {scan.risk.diet_flags.map((f, i) => (
                              <span key={i} className="text-[10px] px-2 py-0.5 bg-amber-50 text-amber-700 rounded-full border border-amber-100 font-medium">
                                {f.diet}: {f.flagged_token}
                              </span>
                            ))}
                          </div>
                        )}

                        <p className="text-xs text-[#888] mt-2">Added {formatDate(item.added_date)}</p>
                      </div>

                      <button onClick={() => handleRemove(item.upc)} disabled={removeMutation.isPending}
                        className="p-2 text-[#888] hover:text-red-500 transition-colors rounded-lg hover:bg-red-50 shrink-0"
                        aria-label="Remove item">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    {isRecalled && product?.recall_info && (
                      <div className="mt-3 pt-3 border-t border-red-100 space-y-1">
                        <p className="text-xs text-red-700"><span className="font-medium">Reason:</span> {product.recall_info.reason}</p>
                        <p className="text-xs text-red-700"><span className="font-medium">Class:</span> {product.recall_info.hazard_classification}</p>
                        {product.recall_info.recall_date && <p className="text-xs text-red-700"><span className="font-medium">Date:</span> {product.recall_info.recall_date}</p>}
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
        <Link to="/groceries-example" className="text-xs text-[#888] hover:text-black transition-colors">View demo example →</Link>
      </div>
    </div>
  );
};
