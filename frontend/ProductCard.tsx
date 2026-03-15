/**
 * Product card: name, brand, verdict badge, risk notifications, recall details, and add-to-cart.
 */
import { AlertCircle, CheckCircle, ShoppingCart, ShieldAlert, ShieldX } from 'lucide-react';
import type { Product } from './types';
import { RecallAlert } from './RecallAlert';

interface ProductCardProps {
  product: Product;
  onAddToCart?: (product: Product) => void;
  showAddButton?: boolean;
}

const verdictBadge = (verdict?: string, isRecalled?: boolean) => {
  if (verdict === 'DONT_BUY' || isRecalled) {
    return (
      <span className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 text-white rounded-full text-xs font-medium shrink-0">
        <ShieldX className="w-3.5 h-3.5" />
        {isRecalled ? 'Recalled' : "Don't buy"}
      </span>
    );
  }
  if (verdict === 'CAUTION') {
    return (
      <span className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500 text-white rounded-full text-xs font-medium shrink-0">
        <ShieldAlert className="w-3.5 h-3.5" />
        Caution
      </span>
    );
  }
  if (verdict === 'OK') {
    return (
      <span className="flex items-center gap-1.5 px-3 py-1.5 text-emerald-700 bg-emerald-50 rounded-full text-xs font-medium shrink-0 border border-emerald-100">
        <CheckCircle className="w-3.5 h-3.5" />
        Safe
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5 px-3 py-1.5 text-[#888] rounded-full text-xs font-medium shrink-0 border border-black/5">
      <AlertCircle className="w-3.5 h-3.5" />
      Unknown
    </span>
  );
};

export const ProductCard = ({ product, onAddToCart, showAddButton = true }: ProductCardProps) => {
  return (
    <div className="rounded-2xl overflow-hidden border border-transparent bg-transparent hover:bg-white hover:border-black/[0.06] transition-colors duration-200">
      <div className="p-6">
        <div className="flex justify-between items-start gap-4 mb-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-[#1A1A1A] mb-1">{product.product_name}</h3>
            <p className="text-[#888] text-sm">{product.brand_name}</p>
          </div>
          {verdictBadge(product.verdict, product.is_recalled)}
        </div>

        <div className="space-y-1 text-sm text-[#888] mb-4">
          <p><span className="font-medium text-[#1A1A1A]">UPC:</span> {product.upc}</p>
          {product.category && <p><span className="font-medium text-[#1A1A1A]">Category:</span> {product.category}</p>}
        </div>

        {/* Risk notifications inline */}
        {product.notifications && product.notifications.length > 0 && (
          <div className="space-y-2 mb-4">
            {product.notifications.slice(0, 3).map((n, i) => (
              <div key={i} className={`rounded-lg px-3 py-2 text-xs ${
                n.severity === 'HIGH' ? 'bg-red-50 text-red-800 border border-red-100' :
                n.severity === 'MEDIUM' ? 'bg-amber-50 text-amber-800 border border-amber-100' :
                'bg-black/[0.02] text-[#555] border border-black/5'
              }`}>
                <span className="font-semibold">{n.title}:</span> {n.message}
              </div>
            ))}
          </div>
        )}

        {product.is_recalled && product.recall_info && <RecallAlert recall={product.recall_info} />}

        {showAddButton && !product.is_recalled && product.verdict !== 'DONT_BUY' && onAddToCart && (
          <button onClick={() => onAddToCart(product)}
            className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium text-[#1A1A1A] border border-black/10 hover:bg-[#1A1A1A] hover:text-white hover:border-[#1A1A1A] transition-colors duration-200">
            <ShoppingCart className="w-4 h-4" /> Add to My Groceries
          </button>
        )}
      </div>
    </div>
  );
};
