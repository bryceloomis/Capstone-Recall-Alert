/**
 * ReceiptReviewModal: shown after receipt OCR completes.
 * Displays recalled items as warnings, safe items as confirmation,
 * then lets the user dismiss. Cart saving happens on the backend during scan.
 */
import { AlertTriangle, CheckCircle, X, ShoppingCart, Package } from 'lucide-react';
import type { ReceiptScanResult } from './api';

interface Props {
  result: ReceiptScanResult;
  isSignedIn: boolean;
  onDone: (cartItemsAdded: number) => void;
  onClose: () => void;
}

export function ReceiptReviewModal({ result, isSignedIn, onDone, onClose }: Props) {
  const { matched_recalls, safe_items, cart_items_added, total_lines } = result;
  const totalFound = matched_recalls.length + safe_items.length;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="bg-cream w-full sm:max-w-lg sm:rounded-2xl rounded-t-2xl max-h-[90vh] flex flex-col shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-4 border-b border-black/5 shrink-0">
          <div>
            <h2 className="text-lg font-semibold text-black">Receipt scanned</h2>
            <p className="text-xs text-[#888] mt-0.5">
              {totalFound} item{totalFound !== 1 ? 's' : ''} found from {total_lines} lines
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-[#888] hover:text-black transition-colors rounded-lg hover:bg-black/5"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5 min-h-0">

          {/* Nothing found at all */}
          {totalFound === 0 && (
            <div className="text-center py-8">
              <Package className="w-10 h-10 text-black/20 mx-auto mb-3" />
              <p className="text-sm font-medium text-black">No items found</p>
              <p className="text-xs text-[#888] mt-1">
                Try a clearer photo with better lighting.
              </p>
            </div>
          )}

          {/* Recalled items — shown as warnings */}
          {matched_recalls.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-red-700 flex items-center gap-2 mb-3">
                <AlertTriangle className="w-4 h-4" />
                Recall alerts ({matched_recalls.length})
              </h3>
              <div className="space-y-2">
                {matched_recalls.map((item, idx) => (
                  <div key={idx} className="p-3 rounded-xl border border-red-200 bg-red-50">
                    <p className="text-sm font-medium text-black leading-snug">{item.product_name}</p>
                    {item.brand_name && (
                      <p className="text-xs text-[#888]">{item.brand_name}</p>
                    )}
                    <p className="text-xs text-red-700 mt-1 leading-relaxed">
                      <span className="font-medium">Reason: </span>{item.recall_info.reason}
                    </p>
                    <p className="text-xs text-[#888] mt-1">
                      {item.recall_info.severity && <span className="mr-2">{item.recall_info.severity}</span>}
                      {item.recall_info.recall_date}
                    </p>
                    <p className="text-xs text-[#888]/60 mt-1 italic">from receipt: "{item.raw_text}"</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Safe items — saved to cart */}
          {safe_items.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-black flex items-center gap-2 mb-3">
                <CheckCircle className="w-4 h-4 text-emerald-600" />
                No recalls found ({safe_items.length})
              </h3>
              <div className="rounded-xl bg-black/[0.03] border border-black/5 px-4 py-3 space-y-1">
                {safe_items.map((item, idx) => (
                  <p key={idx} className="text-xs text-[#888]">{item.cleaned_text}</p>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 pb-5 pt-4 border-t border-black/5 shrink-0 space-y-3">
          {isSignedIn && totalFound > 0 && (
            <p className="text-xs text-center text-emerald-700">
              {cart_items_added > 0
                ? `✓ ${cart_items_added} item${cart_items_added !== 1 ? 's' : ''} saved to My Groceries`
                : '✓ Items already in your grocery list'}
            </p>
          )}
          {!isSignedIn && (
            <p className="text-xs text-center text-[#888]">
              Sign in to save items to your grocery list.
            </p>
          )}
          <button
            onClick={() => onDone(cart_items_added)}
            className="w-full flex items-center justify-center gap-2 py-3 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity"
          >
            <ShoppingCart className="w-4 h-4" />
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
