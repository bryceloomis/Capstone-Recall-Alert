/** V2 static Settings: ingredient restrictions + notification toggles (demo). */
import { Link } from 'react-router-dom';
import { useState } from 'react';

export function V2Settings() {
  const [restrictions, setRestrictions] = useState(['high fructose corn syrup']);
  const [newRestriction, setNewRestriction] = useState('');

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h2 className="text-xl font-semibold text-black">Settings (V2)</h2>
        <p className="text-neutral-500 text-sm mt-1">
          Notification preferences and ingredient restrictions (static demo).
        </p>
      </div>

      <section className="border border-neutral-200 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-black mb-4">Ingredients to avoid</h3>
        <p className="text-sm text-neutral-600 mb-4">
          Add ingredients you want to avoid (e.g. artificial colors).
        </p>
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

      <section className="border border-neutral-200 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-black mb-4">Notifications</h3>
        <div className="space-y-3">
          <label className="flex items-center justify-between">
            <span className="text-sm text-neutral-700">In-app alerts</span>
            <input type="checkbox" defaultChecked className="w-4 h-4 rounded border-neutral-300" />
          </label>
          <label className="flex items-center justify-between">
            <span className="text-sm text-neutral-700">Browser push</span>
            <input type="checkbox" className="w-4 h-4 rounded border-neutral-300" />
          </label>
        </div>
      </section>

      <Link to="/v2" className="inline-block text-sm font-medium text-neutral-500 hover:text-black">
        Back to home
      </Link>
    </div>
  );
}
