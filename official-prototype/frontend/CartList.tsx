/**
 * Renders backend cart items with Check and Remove; empty state when no items.
 */
import { ShoppingCart, Trash2 } from 'lucide-react';
import type { CartItem } from './types';

interface CartListProps {
  items: CartItem[];
  onRemove: (upc: string) => void;
  onCheckItem: (upc: string) => void;
  isLoading?: boolean;
}

export const CartList = ({ items, onRemove, onCheckItem, isLoading = false }: CartListProps) => {
  if (items.length === 0) {
    return (
      <div className="text-center py-14">
        <ShoppingCart className="w-12 h-12 text-[#888] mx-auto mb-3" />
        <p className="text-[#888] font-medium">Your list is empty</p>
        <p className="text-[#888] text-sm mt-1">
          Search or scan products to add them.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div
          key={item.upc}
          className="flex items-center justify-between rounded-xl p-4 border border-transparent hover:bg-white hover:border-black/[0.06] transition-colors duration-200"
        >
          <div className="flex-1 min-w-0 mr-4">
            <h4 className="font-medium text-black truncate">{item.product_name}</h4>
            <p className="text-sm text-[#888] truncate">{item.brand_name}</p>
            <p className="text-xs text-[#888] mt-1">UPC: {item.upc}</p>
            <p className="text-xs text-[#888]">
              Added {new Date(item.added_date).toLocaleDateString()}
            </p>
          </div>
          <div className="flex gap-2 shrink-0">
            <button
              onClick={() => onCheckItem(item.upc)}
              disabled={isLoading}
              className="px-4 py-2 rounded-lg text-sm font-medium text-[#1A1A1A] border border-black/10 hover:bg-[#1A1A1A] hover:text-white hover:border-[#1A1A1A] disabled:opacity-40 transition-colors duration-200"
            >
              Check
            </button>
            <button
              onClick={() => onRemove(item.upc)}
              disabled={isLoading}
              className="p-2 text-[#888] hover:text-black hover:bg-black/5 rounded-lg transition-colors disabled:opacity-40"
              title="Remove"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};
