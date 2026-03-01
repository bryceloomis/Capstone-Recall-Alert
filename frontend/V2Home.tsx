/**
 * V2 static hub: cards for Scan barcode, Scan receipt, and Cart scan (links to /v2/demo step flow).
 */
import { Link } from 'react-router-dom';
import { Camera, Receipt, ShoppingCart } from 'lucide-react';

export function V2Home() {
  return (
    <div className="space-y-10">
      <div>
        <h2 className="text-xl font-semibold text-black mb-1">V2 – Ingredient preferences & tracking</h2>
        <p className="text-[#888] text-sm">
          Stretch goal demo. Build a grocery profile and get recall + ingredient match alerts.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link
          to="/v2/scan"
          className="block bg-white rounded-2xl p-6 border border-black/5 hover:border-black/10 transition-colors"
        >
          <Camera className="w-10 h-10 text-[#888] mb-4" />
          <h3 className="font-semibold text-black mb-1">Scan barcode</h3>
          <p className="text-sm text-[#888]">
            Check recall and ingredient match for a single product.
          </p>
        </Link>
        <Link
          to="/v2/scan"
          className="block bg-white rounded-2xl p-6 border border-black/5 hover:border-black/10 transition-colors"
        >
          <Receipt className="w-10 h-10 text-[#888] mb-4" />
          <h3 className="font-semibold text-black mb-1">Scan receipt</h3>
          <p className="text-sm text-[#888]">
            Add multiple items at once; recall + ingredient check on all.
          </p>
        </Link>
        <Link
          to="/v2/demo"
          className="block bg-white rounded-2xl p-6 border border-black/5 hover:border-black/10 transition-colors"
        >
          <ShoppingCart className="w-10 h-10 text-[#888] mb-4" />
          <h3 className="font-semibold text-black mb-1">Cart scan + ingredient preferences demo</h3>
          <p className="text-sm text-[#888]">
            Walk through a mock cart result with ingredient match and recommendations. Use the arrows in the top bar.
          </p>
        </Link>
      </div>

      <div className="pt-6 border-t border-black/10">
        <h3 className="text-sm font-semibold text-black mb-2">V2 features (static)</h3>
        <ul className="text-sm text-[#888] space-y-1">
          <li>Ingredient preferences (choose ingredients to avoid)</li>
          <li>Ingredient match on scan (with recall status)</li>
          <li>Ingredient restrictions in settings</li>
          <li>Ingredient preferences management</li>
          <li>Alternative product recommendations</li>
        </ul>
      </div>
    </div>
  );
}
