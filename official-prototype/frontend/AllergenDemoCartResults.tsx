/** V2: Ingredient preferences step 2 — mock cart scan results; items flagged if they contain avoided ingredients (no severity). */
import { AlertTriangle } from 'lucide-react';

const MOCK_ITEMS = [
  { name: 'Chocolate granola bars', brand: 'Brand A', flag: 'Contains peanuts' },
  { name: 'Oat milk yogurt', brand: 'Brand B', flag: 'May contain dairy', note: 'Double check label.' },
  { name: 'Mixed nuts trail mix', brand: 'Brand C', flag: 'Contains tree nuts' },
  { name: 'Plain rice crackers', brand: 'Brand D', flag: null },
];

export function AllergenDemoCartResults() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <p className="text-[#888] text-sm mb-1">V2: Ingredient preferences — Step 2</p>
        <h2 className="text-xl font-semibold text-black">Detected items & ingredient match</h2>
        <p className="text-sm text-[#888] mt-2">
          As if you had uploaded a photo of your cart. Items below are flagged when they contain ingredients you chose to avoid.
        </p>
      </div>

      <div className="space-y-3">
        {MOCK_ITEMS.map((item, i) => (
          <div
            key={i}
            className="bg-white rounded-xl p-4 border border-black/5 flex items-start gap-4"
          >
            <div className="flex-1 min-w-0">
              <h3 className="font-medium text-black">{item.name}</h3>
              <p className="text-sm text-[#888]">{item.brand}</p>
              {item.flag && (
                <div className="mt-2 flex items-center gap-2 text-sm text-amber-700">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>Contains avoided ingredients: {item.flag}{item.note ? ` ${item.note}` : ''}</span>
                </div>
              )}
            </div>
            {item.flag && (
              <span className="shrink-0 px-2.5 py-1 rounded-lg text-xs font-medium bg-amber-50 text-amber-800">
                Contains avoided ingredients
              </span>
            )}
          </div>
        ))}
      </div>

      <p className="text-xs text-[#888] pt-2">
        Use the arrows in the top bar to see recommendations or move between steps.
      </p>
    </div>
  );
}
