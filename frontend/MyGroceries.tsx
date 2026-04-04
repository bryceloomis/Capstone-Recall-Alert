/**
 * My Groceries: cart items grouped into trip blocks.
 *
 * Grouping rules:
 *   - source='receipt' → one block per receipt scan session
 *     (all items share the same added_date down to the minute)
 *   - source='barcode' → one block per calendar day
 *
 * Recall status is read from the pre-computed alerts table —
 * no per-item scanning on page load.
 */
import { useMemo, useState } from 'react';
import {
  ShoppingCart, Loader2, LogIn, Trash2,
  CheckCircle, ShieldX, ShieldAlert, ChevronDown, ChevronRight,
  Receipt, ScanLine, Store, Search,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useCart, useRemoveFromCart, useAlerts, useDismissAlert } from './useProduct';
import { getCartRisk } from './api';
import { useStore } from './store';
import type { CartItem } from './types';

// ── Trip grouping ─────────────────────────────────────────────────────────────

interface Trip {
  id: string;
  date: string;           // YYYY-MM-DD, used for display
  type: 'receipt' | 'barcode' | 'manual';
  store_name?: string | null;
  items: CartItem[];
}

function toLocalDateKey(dateStr: string): string {
  // Returns YYYY-MM-DD in local time so items don't cross day boundaries
  const d = new Date(dateStr);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function groupIntoTrips(items: CartItem[]): Trip[] {
  const sorted = [...items].sort(
    (a, b) => new Date(b.added_date).getTime() - new Date(a.added_date).getTime(),
  );

  const trips: Trip[] = [];

  for (const item of sorted) {
    const dateKey = toLocalDateKey(item.added_date);
    const source = item.source ?? 'barcode';

    if (source === 'receipt') {
      // Group receipt items that were added within 5 minutes of each other on the same day
      const existing = trips.find(
        (t) =>
          t.type === 'receipt' &&
          t.date === dateKey &&
          Math.abs(
            new Date(t.items[0].added_date).getTime() - new Date(item.added_date).getTime(),
          ) < 5 * 60 * 1000,
      );
      if (existing) {
        existing.items.push(item);
      } else {
        trips.push({
          id: `receipt-${dateKey}-${trips.length}`,
          date: dateKey,
          type: 'receipt',
          store_name: item.store_name,
          items: [item],
        });
      }
    } else if (source === 'manual') {
      // Manual search items: one block per calendar day
      const existing = trips.find((t) => t.type === 'manual' && t.date === dateKey);
      if (existing) {
        existing.items.push(item);
      } else {
        trips.push({
          id: `manual-${dateKey}`,
          date: dateKey,
          type: 'manual',
          items: [item],
        });
      }
    } else {
      // Barcode items: one block per calendar day
      const existing = trips.find((t) => t.type === 'barcode' && t.date === dateKey);
      if (existing) {
        existing.items.push(item);
      } else {
        trips.push({
          id: `barcode-${dateKey}`,
          date: dateKey,
          type: 'barcode',
          items: [item],
        });
      }
    }
  }

  return trips;
}

function formatTripDate(dateKey: string): string {
  // dateKey is YYYY-MM-DD — parse as local date
  const [y, m, d] = dateKey.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric',
  });
}

// ── Component ──────────────────────────────────────────────────────────────────

export const MyGroceries = () => {
  const userId = useStore((s) => s.userId);
  const userProfile = useStore((s) => s.userProfile);
  const isSignedIn = userProfile != null && (userProfile.name != null || userProfile.email != null);

  const { data: cartData, isLoading: cartLoading } = useCart(userId);
  const { data: alertsData, isLoading: alertsLoading } = useAlerts(userId);
  const { data: riskData, isLoading: riskLoading } = useQuery({
    queryKey: ['cartRisk', userId],
    queryFn: () => getCartRisk(userId!),
    enabled: !!userId && isSignedIn,
    staleTime: 60_000,
  });
  const removeMutation = useRemoveFromCart();
  const dismissMutation = useDismissAlert(userId);

  // Recalled product names from alerts (case-insensitive)
  const recalledNames = useMemo(() => {
    const s = new Set<string>();
    alertsData?.alerts?.forEach((a) => s.add(a.product_name.toLowerCase().trim()));
    return s;
  }, [alertsData]);

  const alertByName = useMemo(() => {
    const m = new Map<string, NonNullable<typeof alertsData>['alerts'][0]>();
    alertsData?.alerts?.forEach((a) => m.set(a.product_name.toLowerCase().trim(), a));
    return m;
  }, [alertsData]);

  const trips = useMemo(
    () => groupIntoTrips(cartData?.cart ?? []),
    [cartData?.cart],
  );

  // Track which trips are open; all start open
  const [openTrips, setOpenTrips] = useState<Set<string>>(() => new Set());
  const allTripIds = useMemo(() => new Set(trips.map((t) => t.id)), [trips]);
  // A trip is open if it's in openTrips OR we haven't seen it before (default open)
  const isTripOpen = (id: string) => !openTrips.has(id);
  const toggleTrip = (id: string) =>
    setOpenTrips((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });

  const handleRemove = async (item: CartItem) => {
    if (!confirm('Remove this item from your list?')) return;
    if (item.upc) {
      await removeMutation.mutateAsync({ userId, upc: item.upc });
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

  const VerdictBadge = ({ verdict, isRecalled }: { verdict?: string | null; isRecalled: boolean }) => {
    if (verdict === 'DONT_BUY' || isRecalled) {
      return <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs font-medium"><ShieldX className="w-3 h-3" />{isRecalled ? 'Recalled' : "Don't buy"}</span>;
    }
    if (verdict === 'CAUTION') {
      return <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs font-medium"><ShieldAlert className="w-3 h-3" />Caution</span>;
    }
    return null;
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

      {/* Not signed in */}
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
              <p className="text-xs text-[#888] mt-1">Scan a product or receipt to add items.</p>
            </div>
          )}

          {!isLoading && trips.length > 0 && (
            <div className="space-y-4">
              {riskLoading && (
                <p className="text-xs text-[#888] flex items-center gap-2">
                  <Loader2 className="w-3 h-3 animate-spin" /> Running risk analysis…
                </p>
              )}
              {trips.map((trip) => {
                const open = isTripOpen(trip.id);
                const recalledCount = trip.items.filter((i) =>
                  recalledNames.has(i.product_name.toLowerCase().trim()),
                ).length;

                return (
                  <div
                    key={trip.id}
                    className={`rounded-xl border overflow-hidden ${
                      recalledCount > 0 ? 'border-red-200' : 'border-black/10'
                    }`}
                  >
                    {/* Trip header — click to collapse/expand */}
                    <button
                      onClick={() => toggleTrip(trip.id)}
                      className="w-full flex items-center justify-between px-4 py-3 bg-black/[0.02] hover:bg-black/[0.04] transition-colors text-left"
                    >
                      <div className="flex items-center gap-3">
                        {trip.type === 'receipt'
                          ? <Receipt className="w-4 h-4 text-[#888] shrink-0" />
                          : trip.type === 'manual'
                            ? <Search className="w-4 h-4 text-[#888] shrink-0" />
                            : <ScanLine className="w-4 h-4 text-[#888] shrink-0" />
                        }
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-medium text-black">
                              {formatTripDate(trip.date)}
                            </span>
                            <span className="text-xs text-[#888]">
                              {trip.type === 'receipt' ? 'Receipt scan' : trip.type === 'manual' ? 'Manual search' : 'Barcode scan'}
                            </span>
                            {trip.store_name && (
                              <span className="flex items-center gap-1 text-xs text-[#888]">
                                <Store className="w-3 h-3" />
                                {trip.store_name}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-xs text-[#888]">
                              {trip.items.length} {trip.items.length === 1 ? 'item' : 'items'}
                            </span>
                            {recalledCount > 0 && (
                              <span className="text-xs font-medium text-red-600">
                                · {recalledCount} recalled
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      {open
                        ? <ChevronDown className="w-4 h-4 text-[#888] shrink-0" />
                        : <ChevronRight className="w-4 h-4 text-[#888] shrink-0" />
                      }
                    </button>

                    {/* Trip items */}
                    {open && (
                      <div className="divide-y divide-black/5">
                        {trip.items.map((item) => {
                          const key = item.product_name.toLowerCase().trim();
                          const isRecalled = recalledNames.has(key);
                          const alert = alertByName.get(key);
                          const risk = item.upc ? riskData?.results?.[item.upc] : undefined;
                          const verdict = isRecalled ? 'DONT_BUY' : (risk?.verdict ?? null);
                          const notifications = risk?.notifications ?? [];

                          return (
                            <div
                              key={`${item.upc ?? item.product_name}-${item.added_date}`}
                              className={`px-4 py-3 bg-white ${
                                verdict === 'DONT_BUY' ? 'bg-red-50/30' :
                                verdict === 'CAUTION' ? 'bg-amber-50/20' : ''
                              }`}
                            >
                              <div className="flex items-start justify-between gap-4">
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className="text-sm font-medium text-black">
                                      {item.product_name}
                                    </span>
                                    <VerdictBadge verdict={verdict} isRecalled={isRecalled} />
                                  </div>
                                  {item.brand_name && (
                                    <p className="text-xs text-[#888] mt-0.5">{item.brand_name}</p>
                                  )}

                                  {/* Risk notifications (allergen, diet, additive) */}
                                  {!isRecalled && notifications.length > 0 && (
                                    <div className="mt-2 space-y-1">
                                      {notifications.slice(0, 3).map((n, i) => (
                                        <p key={i} className={`text-xs px-2 py-1 rounded ${
                                          n.severity === 'HIGH' ? 'bg-red-50 text-red-700' :
                                          n.severity === 'MEDIUM' ? 'bg-amber-50 text-amber-700' :
                                          'bg-black/[0.02] text-[#555]'
                                        }`}>
                                          <span className="font-medium">{n.title}:</span>{' '}
                                          {n.summary || n.message}
                                        </p>
                                      ))}
                                    </div>
                                  )}

                                  {/* Recall details + dismiss */}
                                  {isRecalled && alert && (
                                    <div className="mt-2 space-y-1.5">
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
                                          <span className="font-medium">Date:</span>{' '}
                                          {formatDate(String(alert.recall.recall_date))}
                                        </p>
                                      )}
                                      <button
                                        onClick={() => dismissMutation.mutate(alert.alert_id)}
                                        disabled={dismissMutation.isPending}
                                        className="mt-1 text-xs text-[#888] underline underline-offset-2 hover:text-black transition-colors disabled:opacity-50"
                                      >
                                        That's not my product
                                      </button>
                                    </div>
                                  )}
                                </div>
                                <button
                                  onClick={() => handleRemove(item)}
                                  disabled={removeMutation.isPending}
                                  className="p-2 text-[#888] hover:text-red-500 transition-colors rounded-lg hover:bg-red-50 shrink-0"
                                  aria-label="Remove item"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

    </div>
  );
};
