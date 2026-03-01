/** V2 static My Groceries page (demo copy only). */
import { Link } from 'react-router-dom';
import { ShoppingCart } from 'lucide-react';

export function V2Groceries() {
  const mockItems = [
    { name: 'Granola Bar', brand: 'Brand A', ingredientsToAvoid: ['Peanuts'], upc: '123' },
    { name: 'Cereal', brand: 'Brand B', ingredientsToAvoid: [] as string[], upc: '456' },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShoppingCart className="w-7 h-7 text-black" />
          <h2 className="text-xl font-semibold text-black">My Groceries (V2)</h2>
        </div>
        <span className="px-3 py-1.5 bg-neutral-100 text-neutral-700 rounded-full text-sm font-medium">
          {mockItems.length} items
        </span>
      </div>

      <p className="text-sm text-neutral-500">
        V2: list with ingredient preferences; check each item for recall + ingredient match.
      </p>

      <div className="space-y-3">
        {mockItems.map((item) => (
          <div
            key={item.upc}
            className="flex items-center justify-between bg-neutral-50 rounded-xl p-4 border border-neutral-100"
          >
            <div>
              <h4 className="font-medium text-black">{item.name}</h4>
              <p className="text-sm text-neutral-500">{item.brand}</p>
              {item.ingredientsToAvoid.length > 0 && (
                <p className="text-xs text-neutral-500 mt-1">Contains: {item.ingredientsToAvoid.join(', ')}</p>
              )}
            </div>
            <div className="flex gap-2">
              <span className="px-3 py-1.5 bg-neutral-200 text-neutral-700 rounded-lg text-xs font-medium">
                Check
              </span>
            </div>
          </div>
        ))}
      </div>

      <Link to="/v2" className="inline-block text-sm font-medium text-neutral-500 hover:text-black">
        Back to home
      </Link>
    </div>
  );
}
