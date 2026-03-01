/** V2 static Scan page (demo only; no real scanner). */
import { Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle } from 'lucide-react';

export function V2Scan() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-xl font-semibold text-black">Scan result (V2 demo)</h2>

      {/* Mock ingredient match - PRD UC-2.2 */}
      <div className="rounded-xl border-2 border-amber-200 bg-amber-50 p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-6 h-6 text-amber-600 shrink-0" />
          <div>
            <h3 className="font-semibold text-amber-900">Contains avoided ingredients</h3>
            <p className="text-sm text-amber-800 mt-1">Product contains: Peanuts, Soy</p>
            <p className="text-xs text-amber-700 mt-2">Check the label for your own needs.</p>
          </div>
        </div>
      </div>

      {/* Mock product card with recall status */}
      <div className="bg-neutral-50 rounded-2xl border border-neutral-100 p-6">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="text-lg font-semibold text-black">Sample Product Name</h3>
            <p className="text-neutral-500 text-sm">Brand Name</p>
          </div>
          <span className="flex items-center gap-1.5 px-3 py-1.5 bg-neutral-200 text-neutral-700 rounded-full text-xs font-medium">
            <CheckCircle className="w-3.5 h-3.5" />
            No recall
          </span>
        </div>
        <p className="text-sm text-neutral-600 mb-4">UPC: 041190468831</p>
        <p className="text-xs text-neutral-400">V2 shows ingredient match and recall status (static demo).</p>
      </div>

      {/* Mock recommendations - PRD UC-2.6 */}
      <div className="pt-4 border-t border-neutral-200">
        <h3 className="text-sm font-semibold text-black mb-3">Similar products without these ingredients</h3>
        <div className="space-y-2">
          {['Alternative A – Same category', 'Alternative B – Same category', 'Alternative C – Same category'].map((name, i) => (
            <div key={i} className="flex items-center justify-between bg-neutral-50 rounded-xl px-4 py-3 border border-neutral-100">
              <span className="text-sm font-medium text-black">{name}</span>
              <span className="text-xs text-neutral-400">Tap for details</span>
            </div>
          ))}
        </div>
      </div>

      <Link
        to="/v2"
        className="inline-block text-sm font-medium text-neutral-500 hover:text-black"
      >
        Back to home
      </Link>
    </div>
  );
}
