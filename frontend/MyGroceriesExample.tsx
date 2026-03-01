/**
 * My Groceries Example: demo/mock data showing how recall checking works.
 * Displays "Frequently purchased" sample items (one recalled) to illustrate the feature.
 */
import { AlertCircle, CheckCircle, ShoppingCart } from 'lucide-react';
import { RecallAlert } from './RecallAlert';
import type { Product, RecallInfo } from './types';

/** Demo data; one item is recalled to demonstrate the RecallAlert component. */
const MOCK_ITEMS: (Product & { lastPurchased?: string })[] = [
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

export const MyGroceriesExample = () => {
  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex items-center gap-3">
        <ShoppingCart className="w-7 h-7 text-black" />
        <div>
          <h2 className="text-xl font-semibold text-black">My Groceries Example</h2>
          <p className="text-xs text-[#888] mt-0.5">Demo data — illustrates how recall checking works</p>
        </div>
      </div>

      <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800">
        This page shows example/demo data. Visit{' '}
        <a href="/groceries" className="font-medium underline underline-offset-2">My Groceries</a>
        {' '}to see your real saved products.
      </div>

      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-black">Frequently purchased (demo)</h3>
        <p className="text-sm text-[#888]">
          Here's how your grocery list would look. Items are automatically checked against the recall database.
        </p>
        <div className="space-y-3">
          {MOCK_ITEMS.map((item) => (
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

      <section className="pt-6 border-t border-black/10">
        <h3 className="text-sm font-semibold text-black mb-2">How it works</h3>
        <ul className="text-sm text-[#888] space-y-1">
          <li>Add products by scanning their barcode or searching by name.</li>
          <li>Your list is automatically checked against the FDA & USDA recall database.</li>
          <li>You'll be alerted when any item you've saved is recalled.</li>
        </ul>
      </section>
    </div>
  );
};
