/**
 * Full-screen modal shown after a barcode scan.
 * Shows product info from Open Food Facts + recall status from our DB.
 */
import { X, AlertTriangle, CheckCircle, ShoppingCart, Camera, Package } from 'lucide-react';
import type { Product } from './types';

interface ScanResultModalProps {
  product: Product;
  isSignedIn: boolean;
  onAddToCart: (product: Product) => void;
  onScanAgain: () => void;
  onClose: () => void;
  isAdding?: boolean;
}

export const ScanResultModal = ({
  product,
  isSignedIn,
  onAddToCart,
  onScanAgain,
  onClose,
  isAdding = false,
}: ScanResultModalProps) => {
  const recalled = product.is_recalled;

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-black/10 shrink-0">
        <p className="text-xs text-[#888] font-mono">UPC {product.upc}</p>
        <button
          onClick={onClose}
          className="p-2 text-[#888] hover:text-black transition-colors rounded-lg hover:bg-black/5"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto">

        {/* Recall status banner */}
        {recalled ? (
          <div className="bg-red-600 px-6 py-5 flex items-center gap-4">
            <div className="p-2 bg-white/20 rounded-full shrink-0">
              <AlertTriangle className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="text-white font-bold text-lg leading-tight">Active Recall</p>
              <p className="text-red-100 text-sm mt-0.5">
                {product.recall_info?.hazard_classification ?? ''} — Do not consume
              </p>
            </div>
          </div>
        ) : (
          <div className="bg-emerald-600 px-6 py-5 flex items-center gap-4">
            <div className="p-2 bg-white/20 rounded-full shrink-0">
              <CheckCircle className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="text-white font-bold text-lg leading-tight">No Active Recall</p>
              <p className="text-emerald-100 text-sm mt-0.5">Not found in current recall database</p>
            </div>
          </div>
        )}

        <div className="px-5 py-6 space-y-6">

          {/* Product info row */}
          <div className="flex gap-4 items-start">
            {/* Image or placeholder */}
            <div className="w-20 h-20 rounded-xl border border-black/10 bg-black/[0.02] flex items-center justify-center shrink-0 overflow-hidden">
              {product.image_url ? (
                <img
                  src={product.image_url}
                  alt={product.product_name}
                  className="w-full h-full object-contain"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
              ) : (
                <Package className="w-8 h-8 text-black/20" />
              )}
            </div>

            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-semibold text-black leading-tight">
                {product.product_name}
              </h2>
              {product.brand_name && (
                <p className="text-sm text-[#888] mt-0.5">{product.brand_name}</p>
              )}
              {product.category && (
                <p className="text-xs text-[#888] mt-1">{product.category}</p>
              )}
            </div>
          </div>

          {/* Recall details */}
          {recalled && product.recall_info && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 space-y-2">
              <p className="text-sm font-semibold text-red-800">Recall details</p>
              <dl className="space-y-1.5 text-sm">
                <div className="flex gap-2">
                  <dt className="text-red-600 font-medium w-20 shrink-0">Reason</dt>
                  <dd className="text-red-900">{product.recall_info.reason}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="text-red-600 font-medium w-20 shrink-0">Class</dt>
                  <dd className="text-red-900">{product.recall_info.hazard_classification}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="text-red-600 font-medium w-20 shrink-0">Date</dt>
                  <dd className="text-red-900">{product.recall_info.recall_date}</dd>
                </div>
                {product.recall_info.firm_name && (
                  <div className="flex gap-2">
                    <dt className="text-red-600 font-medium w-20 shrink-0">Firm</dt>
                    <dd className="text-red-900">{product.recall_info.firm_name}</dd>
                  </div>
                )}
              </dl>
            </div>
          )}

          {/* Ingredients */}
          {product.ingredients && product.ingredients.length > 0 && (
            <div>
              <p className="text-sm font-semibold text-black mb-2">Ingredients</p>
              <p className="text-xs text-[#888] leading-relaxed">
                {product.ingredients.join(', ')}
              </p>
            </div>
          )}

        </div>
      </div>

      {/* Footer buttons */}
      <div className="shrink-0 px-5 py-4 border-t border-black/10 space-y-3 bg-white">
        {!recalled && (
          isSignedIn ? (
            <button
              onClick={() => onAddToCart(product)}
              disabled={isAdding}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              <ShoppingCart className="w-4 h-4" />
              {isAdding ? 'Adding…' : 'Add to My Groceries'}
            </button>
          ) : (
            <p className="text-center text-sm text-[#888]">
              <button
                onClick={onClose}
                className="text-black font-medium underline underline-offset-2"
              >
                Sign in
              </button>
              {' '}to save this to your grocery list
            </p>
          )
        )}
        <button
          onClick={onScanAgain}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-black/5 text-black rounded-xl text-sm font-medium hover:bg-black/10 transition-colors"
        >
          <Camera className="w-4 h-4" />
          Scan another
        </button>
      </div>
    </div>
  );
};
