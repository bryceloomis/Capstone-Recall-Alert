/** V2: Ingredient preferences step 5 — ingredients to avoid (demo). */
import { useState } from 'react';

export function V2DemoRestrictions() {
  const [restrictions, setRestrictions] = useState(['high fructose corn syrup']);
  const [newRestriction, setNewRestriction] = useState('');

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <p className="text-[#888] text-sm">V2: Ingredient preferences — Step 5</p>
        <h2 className="text-xl font-semibold text-[#1A1A1A] mt-1">Ingredients to avoid</h2>
        <p className="text-[#888] text-sm mt-1">
          Add ingredients you want to avoid (e.g. artificial colors).
        </p>
      </div>

      <section className="border border-neutral-200 rounded-xl p-6">
        <ul className="space-y-2 mb-4">
          {restrictions.map((r, i) => (
            <li key={i} className="flex items-center justify-between bg-neutral-50 rounded-lg px-4 py-2">
              <span className="text-sm text-black">{r}</span>
              <button type="button" className="text-neutral-400 hover:text-black text-sm">
                Remove
              </button>
            </li>
          ))}
        </ul>
        <div className="flex gap-2">
          <input
            type="text"
            value={newRestriction}
            onChange={(e) => setNewRestriction(e.target.value)}
            placeholder="e.g. artificial colors"
            className="flex-1 px-4 py-2.5 bg-white border border-neutral-200 rounded-xl text-black placeholder-neutral-400 focus:outline-none focus:border-neutral-400"
          />
          <button
            type="button"
            className="px-4 py-2.5 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90"
          >
            Add
          </button>
        </div>
      </section>
    </div>
  );
}
