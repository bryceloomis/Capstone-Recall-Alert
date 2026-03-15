/**
 * Full-screen modal shown after a barcode scan.
 * Displays verdict, notifications, allergen matches, diet flags, recall summary,
 * and product info from GET /api/risk/scan/{upc}.
 */
import {
  X, AlertTriangle, CheckCircle, ShoppingCart, Camera, Package,
  ShieldAlert, ShieldCheck, ShieldX, AlertCircle, Wheat, Leaf,
} from 'lucide-react';
import type { ScanResponse, Product, RiskNotification, AllergenMatch, DietFlag } from './types';

interface ScanResultModalProps {
  scan: ScanResponse | null;
  product: Product;
  isSignedIn: boolean;
  onAddToCart: (product: Product) => void;
  onScanAgain: () => void;
  onClose: () => void;
  isAdding?: boolean;
}

const verdictConfig = {
  OK: {
    icon: ShieldCheck,
    bg: 'bg-emerald-600',
    label: 'Safe to consume',
    sub: 'No recalls, allergens, or diet conflicts found',
    textLight: 'text-emerald-100',
  },
  CAUTION: {
    icon: ShieldAlert,
    bg: 'bg-amber-500',
    label: 'Use caution',
    sub: 'Potential concerns detected — review details below',
    textLight: 'text-amber-100',
  },
  DONT_BUY: {
    icon: ShieldX,
    bg: 'bg-red-600',
    label: 'Do not buy',
    sub: 'Critical issues found — see details below',
    textLight: 'text-red-100',
  },
} as const;

function NotificationCard({ n }: { n: RiskNotification }) {
  const colors = {
    HIGH: 'border-red-200 bg-red-50 text-red-900',
    MEDIUM: 'border-amber-200 bg-amber-50 text-amber-900',
    LOW: 'border-black/10 bg-black/[0.02] text-black',
  };
  const icons = {
    RECALL: AlertTriangle,
    ALLERGEN: Wheat,
    DIET: Leaf,
    ADDITIVE: AlertCircle,
    WARNING: AlertCircle,
  };
  const Icon = icons[n.type] ?? AlertCircle;

  return (
    <div className={`rounded-xl border p-3.5 ${colors[n.severity]}`}>
      <div className="flex items-start gap-3">
        <Icon className="w-4 h-4 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold">{n.title}</p>
          <p className="text-xs mt-0.5 opacity-80">{n.message}</p>
        </div>
        <span className="text-[10px] font-mono uppercase opacity-50 shrink-0">{n.type}</span>
      </div>
    </div>
  );
}

function AllergenSection({ matches }: { matches: AllergenMatch[] }) {
  if (!matches.length) return null;
  return (
    <div>
      <p className="text-sm font-semibold text-black mb-2 flex items-center gap-2">
        <Wheat className="w-4 h-4" />
        Allergen matches ({matches.length})
      </p>
      <div className="space-y-2">
        {matches.map((m, i) => (
          <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-red-50 border border-red-100">
            <div className="flex-1 min-w-0">
              <span className="text-sm font-medium text-red-900">{m.allergen}</span>
              <span className="text-xs text-red-700 ml-2">matched "{m.matched_token}"</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {m.is_advisory && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-medium">advisory</span>
              )}
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                m.confidence === 'DEFINITE' ? 'bg-red-200 text-red-800' :
                m.confidence === 'PROBABLE' ? 'bg-amber-200 text-amber-800' :
                'bg-gray-200 text-gray-700'
              }`}>{m.confidence}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DietSection({ flags }: { flags: DietFlag[] }) {
  if (!flags.length) return null;
  return (
    <div>
      <p className="text-sm font-semibold text-black mb-2 flex items-center gap-2">
        <Leaf className="w-4 h-4" />
        Diet conflicts ({flags.length})
      </p>
      <div className="space-y-2">
        {flags.map((f, i) => (
          <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-amber-50 border border-amber-100">
            <div className="flex-1 min-w-0">
              <span className="text-sm font-medium text-amber-900">{f.diet}</span>
              <span className="text-xs text-amber-700 ml-2">"{f.flagged_token}" — {f.reason}</span>
            </div>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0 ${
              f.confidence === 'DEFINITE' ? 'bg-red-200 text-red-800' :
              f.confidence === 'PROBABLE' ? 'bg-amber-200 text-amber-800' :
              'bg-gray-200 text-gray-700'
            }`}>{f.confidence}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export const ScanResultModal = ({
  scan,
  product,
  isSignedIn,
  onAddToCart,
  onScanAgain,
  onClose,
  isAdding = false,
}: ScanResultModalProps) => {
  const verdict = scan?.verdict ?? (product.is_recalled ? 'DONT_BUY' : 'OK');
  const vc = verdictConfig[verdict] ?? verdictConfig.OK;
  const VerdictIcon = vc.icon;
  const notifications = scan?.notifications ?? product.notifications ?? [];
  const risk = scan?.risk ?? product.risk;
  const recallSummary = scan?.recall?.summary;

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-black/10 shrink-0">
        <p className="text-xs text-[#888] font-mono">UPC {product.upc}</p>
        <button onClick={onClose} className="p-2 text-[#888] hover:text-black transition-colors rounded-lg hover:bg-black/5" aria-label="Close">
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto">

        {/* Verdict banner */}
        <div className={`${vc.bg} px-6 py-5 flex items-center gap-4`}>
          <div className="p-2 bg-white/20 rounded-full shrink-0">
            <VerdictIcon className="w-6 h-6 text-white" />
          </div>
          <div>
            <p className="text-white font-bold text-lg leading-tight">{vc.label}</p>
            <p className={`${vc.textLight} text-sm mt-0.5`}>{vc.sub}</p>
          </div>
        </div>

        <div className="px-5 py-6 space-y-6">

          {/* Product info */}
          <div className="flex gap-4 items-start">
            <div className="w-20 h-20 rounded-xl border border-black/10 bg-black/[0.02] flex items-center justify-center shrink-0 overflow-hidden">
              {product.image_url ? (
                <img src={product.image_url} alt={product.product_name} className="w-full h-full object-contain"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
              ) : (
                <Package className="w-8 h-8 text-black/20" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-semibold text-black leading-tight">{product.product_name}</h2>
              {product.brand_name && <p className="text-sm text-[#888] mt-0.5">{product.brand_name}</p>}
              {product.category && <p className="text-xs text-[#888] mt-1">{product.category}</p>}
            </div>
          </div>

          {/* Explanation bullets */}
          {scan?.explanation && scan.explanation.length > 0 && (
            <div className="rounded-xl border border-black/10 bg-black/[0.02] p-4">
              <p className="text-sm font-semibold text-black mb-2">Analysis</p>
              <ul className="space-y-1.5">
                {scan.explanation.map((e, i) => (
                  <li key={i} className="text-sm text-[#555] flex gap-2">
                    <span className="text-black/30 shrink-0">•</span>
                    <span>{e}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Notifications */}
          {notifications.length > 0 && (
            <div className="space-y-2">
              {notifications.map((n, i) => <NotificationCard key={i} n={n} />)}
            </div>
          )}

          {/* Recall details with summary */}
          {product.is_recalled && product.recall_info && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 space-y-3">
              <p className="text-sm font-semibold text-red-800">Recall details</p>
              {recallSummary && (
                <div className="space-y-2 text-sm text-red-900">
                  <p className="font-semibold">{recallSummary.headline}</p>
                  <p><span className="font-medium">What happened: </span>{recallSummary.what_happened}</p>
                  <p><span className="font-medium">What to do: </span>{recallSummary.what_to_do}</p>
                  <p><span className="font-medium">Who is at risk: </span>{recallSummary.who_is_at_risk}</p>
                </div>
              )}
              <dl className="space-y-1.5 text-sm">
                <div className="flex gap-2">
                  <dt className="text-red-600 font-medium w-20 shrink-0">Reason</dt>
                  <dd className="text-red-900">{product.recall_info.reason}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="text-red-600 font-medium w-20 shrink-0">Class</dt>
                  <dd className="text-red-900">{product.recall_info.hazard_classification}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="text-red-600 font-medium w-20 shrink-0">Date</dt>
                  <dd className="text-red-900">{product.recall_info.recall_date}</dd>
                </div>
                {product.recall_info.firm_name && (
                  <div className="flex gap-2">
                    <dt className="text-red-600 font-medium w-20 shrink-0">Firm</dt>
                    <dd className="text-red-900">{product.recall_info.firm_name}</dd>
                  </div>
                )}
              </dl>
            </div>
          )}

          {/* Allergen matches */}
          {risk?.allergen_matches && <AllergenSection matches={risk.allergen_matches} />}

          {/* Diet flags */}
          {risk?.diet_flags && <DietSection flags={risk.diet_flags} />}

          {/* Ingredients */}
          {product.ingredients && product.ingredients.length > 0 && (
            <div>
              <p className="text-sm font-semibold text-black mb-2">Ingredients</p>
              <p className="text-xs text-[#888] leading-relaxed">{product.ingredients.join(', ')}</p>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="shrink-0 px-5 py-4 border-t border-black/10 space-y-3 bg-white">
        {verdict === 'OK' && (
          isSignedIn ? (
            <button onClick={() => onAddToCart(product)} disabled={isAdding}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50">
              <ShoppingCart className="w-4 h-4" />
              {isAdding ? 'Adding…' : 'Add to My Groceries'}
            </button>
          ) : (
            <p className="text-center text-sm text-[#888]">
              <button onClick={onClose} className="text-black font-medium underline underline-offset-2">Sign in</button>
              {' '}to save this to your grocery list
            </p>
          )
        )}
        <button onClick={onScanAgain}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-black/5 text-black rounded-xl text-sm font-medium hover:bg-black/10 transition-colors">
          <Camera className="w-4 h-4" />
          Scan another
        </button>
      </div>
    </div>
  );
};
