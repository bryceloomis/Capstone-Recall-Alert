/**
 * Home: three primary actions — Scan, Search, Saved — with smooth hover reveals.
 */
import { useState, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Camera, Receipt, Search, ShoppingBag, Loader2, ChevronRight, Bell, ArrowRight } from 'lucide-react';
import { toast } from './Toast';
import { ManualInput } from './ManualInput';
import { ProductCard } from './ProductCard';
import { useSearchProduct, useAddToCart, useAlerts, useCart } from './useProduct';
import { useStore } from './store';
import type { Product } from './types';

export const Home = () => {
  const [results, setResults] = useState<Product | Product[] | null>(null);
  const [showSearch, setShowSearch] = useState(false);
  const searchMutation = useSearchProduct();
  const addToCartMutation = useAddToCart();
  const userId = useStore((s) => s.userId);
  const userProfile = useStore((s) => s.userProfile);
  const isSignedIn = userProfile != null && (userProfile.name != null || userProfile.email != null);
  const navigate = useNavigate();
  const searchRef = useRef<HTMLDivElement>(null);

  const { data: alertsData } = useAlerts(isSignedIn ? userId : '');
  const { data: cartData } = useCart(isSignedIn ? userId : '');
  const cartUpcs = new Set(cartData?.cart?.map((c) => c.upc) ?? []);

  const handleSearch = async (query: string, type: 'upc' | 'name') => {
    try {
      const result = await searchMutation.mutateAsync(type === 'upc' ? { upc: query } : { name: query });
      setResults(result);
    } catch (error) {
      toast.error((error as Error).message);
      setResults(null);
    }
  };

  const handleAddToCart = async (product: Product) => {
    if (!isSignedIn) {
      toast.error('Please sign in to save items.');
      return;
    }
    try {
      await addToCartMutation.mutateAsync({
        user_id: userId, upc: product.upc,
        product_name: product.product_name, brand_name: product.brand_name,
        added_date: new Date().toISOString(),
      });
      toast.success('Added to My Groceries!');
    } catch (error) {
      toast.error('Error adding to list.');
    }
  };

  const renderResults = () => {
    if (!results) return null;
    const products = Array.isArray(results) ? results : [results];
    return (
      <div className="space-y-6">
        <h2 className="text-xl font-semibold text-[#1A1A1A]">
          {Array.isArray(results) ? 'Search results' : 'Product found'}
        </h2>
        <div className="space-y-4">
          {products.map((product) => (
            <ProductCard key={product.upc} product={product} onAddToCart={handleAddToCart} showAddButton={product.verdict !== 'DONT_BUY'} alreadyInCart={cartUpcs.has(product.upc)} />
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-10">

      {/* Alert banner — only shows when there are real unviewed alerts */}
      {alertsData && alertsData.unviewed_count > 0 && (
        <Link to="/groceries"
          className="block rounded-2xl border border-red-100 bg-red-50/60 hover:bg-red-50 hover:border-red-200 p-4 transition-all duration-300">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-red-100 flex items-center justify-center shrink-0">
              <Bell className="w-4 h-4 text-red-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-[#1A1A1A]">
                {alertsData.unviewed_count} new recall alert{alertsData.unviewed_count > 1 ? 's' : ''}
              </p>
              <p className="text-xs text-[#888] mt-0.5">
                {alertsData.alerts[0]?.product_name} — tap to view
              </p>
            </div>
            <ChevronRight className="w-4 h-4 text-[#ccc] shrink-0" />
          </div>
        </Link>
      )}

      {/* Hero */}
      <div className="pt-2">
        <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-[#1A1A1A] leading-[1.15]">
          Know what's in<br />your food.
        </h1>
        <p className="text-[#888] text-base mt-3 max-w-md">
          Scan, search, or check your saved items for recalls, allergens, and diet conflicts.
        </p>
      </div>

      {/* Action cards */}
      <div className="space-y-4">

        {/* Scan — primary CTA with hover reveal */}
        <ScanCard />

        {/* Search + Saved row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

          {/* Search */}
          <button
            type="button"
            onClick={() => {
              setShowSearch(!showSearch);
              if (!showSearch) {
                setTimeout(() => searchRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 150);
              }
            }}
            className="group relative overflow-hidden rounded-2xl border border-black/[0.08] bg-white p-6 text-left transition-all duration-300 hover:border-black/20 hover:shadow-lg hover:shadow-black/[0.04]"
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="w-10 h-10 rounded-xl bg-[#1A1A1A]/[0.04] flex items-center justify-center mb-4 group-hover:bg-[#1A1A1A]/[0.08] transition-colors duration-300">
                  <Search className="w-5 h-5 text-[#1A1A1A]/60" />
                </div>
                <p className="text-base font-semibold text-[#1A1A1A]">Search</p>
                <p className="text-sm text-[#888] mt-1">Look up by name or UPC</p>
              </div>
              <ArrowRight className="w-5 h-5 text-[#ccc] group-hover:text-[#1A1A1A]/40 group-hover:translate-x-0.5 transition-all duration-300" />
            </div>
          </button>

          {/* Saved */}
          <Link
            to="/groceries"
            className="group relative overflow-hidden rounded-2xl border border-black/[0.08] bg-white p-6 text-left transition-all duration-300 hover:border-black/20 hover:shadow-lg hover:shadow-black/[0.04]"
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="w-10 h-10 rounded-xl bg-[#1A1A1A]/[0.04] flex items-center justify-center mb-4 group-hover:bg-[#1A1A1A]/[0.08] transition-colors duration-300">
                  <ShoppingBag className="w-5 h-5 text-[#1A1A1A]/60" />
                </div>
                <p className="text-base font-semibold text-[#1A1A1A]">Saved Items</p>
                <p className="text-sm text-[#888] mt-1">View your grocery list</p>
              </div>
              <ArrowRight className="w-5 h-5 text-[#ccc] group-hover:text-[#1A1A1A]/40 group-hover:translate-x-0.5 transition-all duration-300" />
            </div>
          </Link>
        </div>
      </div>

      {/* Inline search (revealed on click) */}
      <div
        ref={searchRef}
        className={`transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] overflow-hidden ${
          showSearch ? 'max-h-[600px] opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="pt-2 pb-4">
          <ManualInput onSearch={handleSearch} isLoading={searchMutation.isPending} />
        </div>
      </div>

      {searchMutation.isPending && (
        <div className="flex justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-[#888]" />
        </div>
      )}

      {renderResults()}

      {/* Disclaimer */}
      <div className="pt-6 space-y-2 max-w-lg">
        <p className="text-[11px] text-[#aaa] leading-relaxed">
          This application is an informational tool only. Ingredient matching is based on product databases and AI analysis, and may not be 100% accurate.
        </p>
        <p className="text-[11px] text-[#aaa] leading-relaxed">
          Always read product labels carefully, especially if you have food allergies. When in doubt, consult your healthcare provider.
        </p>
      </div>
    </div>
  );
};

/* ─── Scan Card ──────────────────────────────────────────────── */

function ScanCard() {
  const [hovered, setHovered] = useState(false);
  const navigate = useNavigate();

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="group relative overflow-hidden rounded-2xl border border-black/[0.08] bg-[#1A1A1A] text-white transition-all duration-500 hover:shadow-xl hover:shadow-black/10"
    >
      {/* Desktop: default collapsed state (hidden on mobile) */}
      <div
        className={`hidden md:block p-8 transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
          hovered ? 'opacity-0 translate-y-[-8px] pointer-events-none' : 'opacity-100 translate-y-0'
        }`}
      >
        <div className="flex items-center justify-between">
          <div>
            <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center mb-4">
              <Camera className="w-5 h-5 text-white/80" />
            </div>
            <p className="text-lg font-semibold">Scan a product</p>
            <p className="text-sm text-white/50 mt-1">Barcode or receipt — instant risk check</p>
          </div>
          <ArrowRight className="w-5 h-5 text-white/30 group-hover:text-white/60 transition-colors duration-300" />
        </div>
      </div>

      {/* Desktop: hover reveal (hidden on mobile) */}
      <div
        className={`hidden md:flex absolute inset-0 transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
          hovered ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3 pointer-events-none'
        }`}
      >
        <ScanOption icon={Camera} label="Barcode" sub="Use your camera" onClick={() => navigate('/scan')} border />
        <ScanOption icon={Receipt} label="Receipt" sub="Upload a photo" onClick={() => navigate('/scan')} />
      </div>

      {/* Desktop: spacer for hover height */}
      <div className={`hidden md:block transition-all duration-500 ${hovered ? 'h-[160px]' : 'h-0'}`} />

      {/* Mobile: always show both options */}
      <div className="md:hidden">
        <p className="text-xs font-medium text-white/40 uppercase tracking-wider px-6 pt-5 pb-2">Scan a product</p>
        <div className="flex">
          <ScanOption icon={Camera} label="Barcode" sub="Use your camera" onClick={() => navigate('/scan')} border />
          <ScanOption icon={Receipt} label="Receipt" sub="Upload a photo" onClick={() => navigate('/scan')} />
        </div>
      </div>
    </div>
  );
}

function ScanOption({ icon: Icon, label, sub, onClick, border }: {
  icon: typeof Camera;
  label: string;
  sub: string;
  onClick: () => void;
  border?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 flex flex-col items-center justify-center gap-3 p-6 hover:bg-white/[0.06] active:bg-white/[0.1] transition-colors duration-200 cursor-pointer ${
        border ? 'border-r border-white/10' : ''
      }`}
    >
      <div className="w-12 h-12 rounded-2xl bg-white/10 flex items-center justify-center">
        <Icon className="w-6 h-6 text-white/90" />
      </div>
      <div className="text-center">
        <p className="text-sm font-semibold text-white">{label}</p>
        <p className="text-xs text-white/40 mt-0.5">{sub}</p>
      </div>
    </button>
  );
}
