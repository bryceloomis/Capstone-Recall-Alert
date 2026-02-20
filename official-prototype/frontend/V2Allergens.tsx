/**
 * V2 Ingredient Preferences: choose ingredients to avoid; used as standalone /v2/allergens and as step 4 in /v2/demo flow.
 */
import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

const COMMON_INGREDIENTS_TO_AVOID = [
  'Peanuts', 'Tree nuts', 'Milk', 'Eggs', 'Fish', 'Shellfish', 'Soy', 'Wheat', 'Sesame',
];

export function V2Allergens() {
  const location = useLocation();
  const inStepFlow = location.pathname.startsWith('/v2/demo');
  const [selected, setSelected] = useState<Set<string>>(new Set(['Peanuts', 'Soy']));
  const [custom, setCustom] = useState('');

  const toggle = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        {inStepFlow && <p className="text-[#888] text-sm mb-1">V2: Ingredient preferences — Step 4</p>}
        <h2 className="text-xl font-semibold text-black">Ingredient preferences (V2)</h2>
        <p className="text-neutral-500 text-sm mt-1">
          Choose ingredients to avoid. Used for all scans. Add custom items below.
        </p>
      </div>

      <section>
        <h3 className="text-sm font-semibold text-black mb-3">Common ingredients to avoid</h3>
        <div className="flex flex-wrap gap-2">
          {COMMON_INGREDIENTS_TO_AVOID.map((name) => (
            <button
              key={name}
              onClick={() => toggle(name)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                selected.has(name)
                  ? 'bg-black text-white'
                  : 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200'
              }`}
            >
              {name}
            </button>
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-black mb-2">Add custom ingredient to avoid</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            placeholder="e.g. sulfites, artificial colors"
            className="flex-1 px-4 py-2.5 bg-white border border-neutral-200 rounded-xl text-black placeholder-neutral-400 focus:outline-none focus:border-neutral-400"
          />
          <button
            type="button"
            className="px-4 py-2.5 bg-neutral-100 text-black rounded-xl text-sm font-medium hover:bg-neutral-200"
          >
            Add
          </button>
        </div>
      </section>

      <section>
        <button
          type="button"
          className="px-4 py-2.5 bg-neutral-100 text-black rounded-xl text-sm font-medium hover:bg-neutral-200"
        >
          Test scan (verify detection)
        </button>
        <p className="text-xs text-neutral-400 mt-2">Static demo – no backend.</p>
      </section>

      {!inStepFlow && (
        <Link to="/v2" className="inline-block text-sm font-medium text-neutral-500 hover:text-black">
          Back to home
        </Link>
      )}
    </div>
  );
}
