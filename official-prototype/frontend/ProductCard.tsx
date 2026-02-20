/**
 * Reusable product card: name, brand, recall badge, optional RecallAlert, optional "Add to My Groceries".
 */
import { AlertCircle, CheckCircle, ShoppingCart } from 'lucide-react';
import type { Product } from './types';
import { RecallAlert } from './RecallAlert';

interface ProductCardProps {
  product: Product;
  onAddToCart?: (product: Product) => void;
  showAddButton?: boolean;
}

export const ProductCard = ({ product, onAddToCart, showAddButton = true }: ProductCardProps) => {
  return (
    <div className="rounded-2xl overflow-hidden border border-transparent bg-transparent hover:bg-white hover:border-black/[0.06] transition-colors duration-200">
      <div className="p-6">
        <div className="flex justify-between items-start gap-4 mb-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-[#1A1A1A] mb-1">
              {product.product_name}
            </h3>
            <p className="text-[#888] text-sm">{product.brand_name}</p>
          </div>
          {product.is_recalled ? (
            <span className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1A1A1A] text-white rounded-full text-xs font-medium shrink-0">
              <AlertCircle className="w-3.5 h-3.5" />
              Recalled
            </span>
          ) : (
            <span className="flex items-center gap-1.5 px-3 py-1.5 text-[#888] rounded-full text-xs font-medium shrink-0 border border-black/5 hover:bg-black/[0.04] hover:border-black/10 transition-colors duration-200">
              <CheckCircle className="w-3.5 h-3.5" />
              Safe
            </span>
          )}
        </div>

        <div className="space-y-1 text-sm text-[#888] mb-4">
          <p><span className="font-medium text-[#1A1A1A]">UPC:</span> {product.upc}</p>
          {product.category && (
            <p><span className="font-medium text-[#1A1A1A]">Category:</span> {product.category}</p>
          )}
        </div>

        {product.is_recalled && product.recall_info && (
          <RecallAlert recall={product.recall_info} />
        )}

        {showAddButton && !product.is_recalled && onAddToCart && (
          <button
            onClick={() => onAddToCart(product)}
            className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium text-[#1A1A1A] border border-black/10 hover:bg-[#1A1A1A] hover:text-white hover:border-[#1A1A1A] transition-colors duration-200"
          >
            <ShoppingCart className="w-4 h-4" />
            Add to My Groceries
          </button>
        )}
      </div>
    </div>
  );
};
