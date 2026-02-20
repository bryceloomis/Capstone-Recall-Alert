/** V2: Ingredient preferences step 3 — mock "similar products without your avoided ingredients". */
const MOCK_RECOMMENDATIONS = [
  { ingredient: 'Peanuts', products: ['Peanut-free granola bars – Brand E', 'Sunflower seed bars – Brand F'] },
  { ingredient: 'Dairy', products: ['Coconut yogurt – Brand G', 'Almond yogurt – Brand H'] },
  { ingredient: 'Tree nuts', products: ['Seed-only trail mix – Brand I', 'Dried fruit mix – Brand J'] },
];

export function AllergenDemoRecommendations() {
  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <p className="text-[#888] text-sm mb-1">V2: Ingredient preferences — Step 3</p>
        <h2 className="text-xl font-semibold text-black">Similar products without these ingredients</h2>
        <p className="text-sm text-[#888] mt-2">
          Alternatives you can consider based on the items flagged in your cart.
        </p>
      </div>

      <div className="space-y-6">
        {MOCK_RECOMMENDATIONS.map((group, i) => (
          <div key={i} className="bg-white rounded-xl p-5 border border-black/5">
            <h3 className="text-sm font-semibold text-black mb-3">
              Without {group.ingredient}
            </h3>
            <ul className="space-y-2">
              {group.products.map((name, j) => (
                <li
                  key={j}
                  className="flex items-center justify-between py-2 border-b border-black/5 last:border-0 last:pb-0"
                >
                  <span className="text-sm text-black">{name}</span>
                  <span className="text-xs text-[#888]">View details</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <p className="text-xs text-[#888] pt-2">
        Use the arrows in the top bar to move between steps.
      </p>
    </div>
  );
}
