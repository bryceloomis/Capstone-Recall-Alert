/**
 * ReceiptReviewModal: shown after receipt OCR completes.
 * User reviews matched products (with checkboxes), sees unmatched lines,
 * then confirms to add selected items to their grocery list.
 */
import { useState } from 'react';
import { CheckCircle, X, ShoppingCart, AlertCircle, Loader2, Package } from 'lucide-react';
import type { ReceiptMatchedProduct, ReceiptScanResult } from './api';

interface Props {
  result: ReceiptScanResult;
  isSignedIn: boolean;
  isAdding: boolean;
  onAddSelected: (items: ReceiptMatchedProduct[]) => Promise<void>;
  onClose: () => void;
}

export function ReceiptReviewModal({ result, isSignedIn, isAdding, onAddSelected, onClose }: Props) {
  const [selected, setSelected] = useState<Set<string>>(
    // Pre-select all matched items by default
    new Set(result.matched.map((_, i) => String(i)))
  );

  const toggle = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(String(idx))) next.delete(String(idx));
      else next.add(String(idx));
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(result.matched.map((_, i) => String(i))));
  const clearAll  = () => setSelected(new Set());

  const selectedItems = result.matched.filter((_, i) => selected.has(String(i)));

  const handleAdd = async () => {
    if (selectedItems.length === 0) return;
    await onAddSelected(selectedItems);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="bg-cream w-full sm:max-w-lg sm:rounded-2xl rounded-t-2xl max-h-[90vh] flex flex-col shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-4 border-b border-black/5 shrink-0">
          <div>
            <h2 className="text-lg font-semibold text-black">Receipt results</h2>
            <p className="text-xs text-[#888] mt-0.5">
              {result.matched.length} product{result.matched.length !== 1 ? 's' : ''} found
              {result.unmatched.length > 0 && ` · ${result.unmatched.length} unmatched`}
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

          {/* No matches at all */}
          {result.matched.length === 0 && (
            <div className="text-center py-8">
              <Package className="w-10 h-10 text-black/20 mx-auto mb-3" />
              <p className="text-sm font-medium text-black">No products found</p>
              <p className="text-xs text-[#888] mt-1">
                The receipt text was extracted but no items could be matched to products.
                Try a clearer photo or better lighting.
              </p>
            </div>
          )}

          {/* Matched products */}
          {result.matched.length > 0 && (
            <section>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-black flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-emerald-600" />
                  Matched products
                </h3>
                <div className="flex gap-3 text-xs">
                  <button onClick={selectAll} className="text-[#888] hover:text-black transition-colors">All</button>
                  <button onClick={clearAll}  className="text-[#888] hover:text-black transition-colors">None</button>
                </div>
              </div>

              <div className="space-y-2">
                {result.matched.map((item, idx) => {
                  const isChecked = selected.has(String(idx));
                  return (
                    <label
                      key={idx}
                      className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                        isChecked
                          ? 'bg-white border-black/10'
                          : 'bg-black/[0.02] border-transparent opacity-60'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggle(idx)}
                        className="mt-0.5 w-4 h-4 rounded border-black/20 text-black accent-black shrink-0"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-black leading-snug">{item.product_name}</p>
                        {item.brand_name && (
                          <p className="text-xs text-[#888]">{item.brand_name}</p>
                        )}
                        {item.ingredients.length > 0 && (
                          <p className="text-xs text-[#888] mt-1 leading-relaxed line-clamp-2">
                            <span className="font-medium text-black">Ingredients: </span>
                            {item.ingredients.join(', ')}
                          </p>
                        )}
                        <p className="text-xs text-[#888]/60 mt-1 italic">"{item.raw_text}"</p>
                      </div>
                    </label>
                  );
                })}
              </div>
            </section>
          )}

          {/* Unmatched lines */}
          {result.unmatched.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-black flex items-center gap-2 mb-3">
                <AlertCircle className="w-4 h-4 text-[#888]" />
                Couldn't match ({result.unmatched.length})
              </h3>
              <div className="rounded-xl bg-black/[0.03] border border-black/5 px-4 py-3 space-y-1">
                {result.unmatched.map((line, idx) => (
                  <p key={idx} className="text-xs text-[#888]">{line}</p>
                ))}
              </div>
              <p className="text-xs text-[#888] mt-2">
                These may be produce, deli items, or store-brand products not in the database.
              </p>
            </section>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 pb-5 pt-4 border-t border-black/5 shrink-0 space-y-3">
          {!isSignedIn && (
            <p className="text-xs text-center text-[#888]">
              Sign in to save items to your grocery list.
            </p>
          )}
          <button
            onClick={handleAdd}
            disabled={!isSignedIn || selectedItems.length === 0 || isAdding}
            className="w-full flex items-center justify-center gap-2 py-3 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            {isAdding ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Adding…
              </>
            ) : (
              <>
                <ShoppingCart className="w-4 h-4" />
                Add {selectedItems.length} item{selectedItems.length !== 1 ? 's' : ''} to My Groceries
              </>
            )}
          </button>
          <button
            onClick={onClose}
            className="w-full py-2 text-sm text-[#888] hover:text-black transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
