/**
 * MVP My Groceries: "Frequently purchased" (mock list with one recalled item), User ID + Load list, then CartList from API.
 */
import { useState, useEffect } from 'react';
import { ShoppingCart, Loader2, AlertCircle, CheckCircle } from 'lucide-react';
import { CartList } from './CartList';
import { ProductCard } from './ProductCard';
import { RecallAlert } from './RecallAlert';
import { useCart, useRemoveFromCart, useSearchProduct } from './useProduct';
import { useStore } from './store';
import type { Product, RecallInfo } from './types';

/** Demo data for "Frequently purchased" section; one item is recalled to show RecallAlert. */
const MOCK_FREQUENTLY_PURCHASED: (Product & { lastPurchased?: string })[] = [
  {
    upc: '041190460001',
    product_name: 'Organic peanut butter',
    brand_name: 'Brand A',
    category: 'Pantry',
    is_recalled: false,
    lastPurchased: '2 weeks ago',
  },
  {
    upc: '041190460002',
    product_name: 'Classic granola',
    brand_name: 'Brand B',
    category: 'Cereal',
    is_recalled: true,
    lastPurchased: '1 week ago',
    recall_info: {
      upc: '041190460002',
      product_name: 'Classic granola',
      brand_name: 'Brand B',
      recall_date: '2025-01-15',
      reason: 'Potential contamination with undeclared tree nuts. Check label and manufacturer for details.',
      hazard_classification: 'Class I',
      firm_name: 'Brand B Foods Inc.',
      distribution: 'National',
    } as RecallInfo,
  },
  {
    upc: '041190460003',
    product_name: 'Whole milk yogurt',
    brand_name: 'Brand C',
    category: 'Dairy',
    is_recalled: false,
    lastPurchased: '3 days ago',
  },
  {
    upc: '041190460004',
    product_name: 'Mixed greens salad kit',
    brand_name: 'Brand D',
    category: 'Produce',
    is_recalled: false,
    lastPurchased: '5 days ago',
  },
];

export const MyGroceries = () => {
  const userId = useStore((state) => state.userId);
  const setUserId = useStore((state) => state.setUserId);
  const [userIdInput, setUserIdInput] = useState(userId);
  const [checkedProduct, setCheckedProduct] = useState<Product | null>(null);

  const { data: cartData, isLoading, refetch } = useCart(userId);
  const removeMutation = useRemoveFromCart();
  const searchMutation = useSearchProduct();

  useEffect(() => {
    setUserIdInput(userId);
  }, [userId]);

  const handleLoadCart = () => {
    setUserId(userIdInput);
    refetch();
  };

  const handleRemove = async (upc: string) => {
    if (confirm('Remove this item from your list?')) {
      await removeMutation.mutateAsync({ userId, upc });
    }
  };

  const handleCheckItem = async (upc: string) => {
    try {
      const result = await searchMutation.mutateAsync({ upc });
      if (!Array.isArray(result)) setCheckedProduct(result);
    } catch {
      alert('Error checking product status');
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShoppingCart className="w-7 h-7 text-black" />
          <h2 className="text-xl font-semibold text-black">My Groceries</h2>
        </div>
        {cartData && (
          <span className="px-3 py-1.5 bg-black/5 text-[#888] rounded-full text-sm font-medium">
            {cartData.count} items
          </span>
        )}
      </div>

      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-black">Frequently purchased</h3>
        <p className="text-sm text-[#888]">
          Here’s what you’ve purchased before. We’ll flag any recalls that affect these items.
        </p>
        <div className="space-y-3">
          {MOCK_FREQUENTLY_PURCHASED.map((item) => (
            <div
              key={item.upc}
              className="rounded-xl p-4 border border-transparent hover:bg-white hover:border-black/[0.06] transition-colors duration-200"
            >
              <div className="flex justify-between items-start gap-4">
                <div className="flex-1 min-w-0">
                  <h4 className="font-medium text-black">{item.product_name}</h4>
                  <p className="text-sm text-[#888]">{item.brand_name}</p>
                  {item.lastPurchased && (
                    <p className="text-xs text-[#888] mt-1">Last purchased {item.lastPurchased}</p>
                  )}
                </div>
                {item.is_recalled ? (
                  <span className="flex items-center gap-1.5 px-3 py-1.5 bg-black text-white rounded-full text-xs font-medium shrink-0">
                    <AlertCircle className="w-3.5 h-3.5" />
                    Recalled
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 px-3 py-1.5 bg-black/5 text-[#888] rounded-full text-xs font-medium shrink-0">
                    <CheckCircle className="w-3.5 h-3.5" />
                    No recall
                  </span>
                )}
              </div>
              {item.is_recalled && item.recall_info && (
                <div className="mt-4 pt-4 border-t border-black/10">
                  <RecallAlert recall={item.recall_info} />
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      <div className="rounded-xl p-4 border border-black/5">
        <label className="block text-sm font-medium text-[#1A1A1A] mb-2">
          User ID
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={userIdInput}
            onChange={(e) => setUserIdInput(e.target.value)}
            className="flex-1 px-4 py-2.5 bg-cream border border-black/10 rounded-xl text-black placeholder-[#888] focus:outline-none focus:border-black/20"
            placeholder="Enter your user ID"
          />
          <button
            onClick={handleLoadCart}
            className="px-5 py-2.5 rounded-xl text-sm font-medium text-[#1A1A1A] border border-black/10 hover:bg-[#1A1A1A] hover:text-white hover:border-[#1A1A1A] transition-colors duration-200"
          >
            Load list
          </button>
        </div>
      </div>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-black">Your current list</h3>
        <p className="text-sm text-[#888]">Items you’ve saved to check for recalls.</p>
      </section>

      {isLoading && (
        <div className="flex justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-[#888]" />
        </div>
      )}

      {!isLoading && cartData && (
        <div className="space-y-6">
          <CartList
            items={cartData.cart}
            onRemove={handleRemove}
            onCheckItem={handleCheckItem}
            isLoading={removeMutation.isPending || searchMutation.isPending}
          />
          {checkedProduct && (
            <div className="pt-6 border-t border-black/10">
              <h3 className="text-lg font-semibold text-black mb-4">
                Status check result
              </h3>
              <ProductCard product={checkedProduct} showAddButton={false} />
              <button
                onClick={() => setCheckedProduct(null)}
                className="mt-4 text-sm font-medium text-[#888] hover:text-black transition-colors"
              >
                Close
              </button>
            </div>
          )}
        </div>
      )}

      <section className="pt-6 border-t border-black/10">
        <h3 className="text-sm font-semibold text-black mb-2">How it works</h3>
        <ul className="text-sm text-[#888] space-y-1">
          <li>Add products by scanning or searching.</li>
          <li>Check items for recall status anytime.</li>
          <li>Keep track of products you regularly buy.</li>
        </ul>
      </section>
    </div>
  );
};
