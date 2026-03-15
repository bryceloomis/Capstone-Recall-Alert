/**
 * Home: search by UPC or name, link to scan, and show risk-aware product results.
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Camera, Loader2, AlertCircle, ChevronRight, Bell } from 'lucide-react';
import { ManualInput } from './ManualInput';
import { ProductCard } from './ProductCard';
import { useSearchProduct, useAddToCart, useAlerts } from './useProduct';
import { useStore } from './store';
import type { Product } from './types';

export const Home = () => {
  const [results, setResults] = useState<Product | Product[] | null>(null);
  const searchMutation = useSearchProduct();
  const addToCartMutation = useAddToCart();
  const userId = useStore((s) => s.userId);
  const userProfile = useStore((s) => s.userProfile);
  const isSignedIn = userProfile != null && (userProfile.name != null || userProfile.email != null);

  const { data: alertsData } = useAlerts(isSignedIn ? userId : '');

  const handleSearch = async (query: string, type: 'upc' | 'name') => {
    try {
      const result = await searchMutation.mutateAsync(type === 'upc' ? { upc: query } : { name: query });
      setResults(result);
    } catch (error) {
      alert('Error: ' + (error as Error).message);
      setResults(null);
    }
  };

  const handleAddToCart = async (product: Product) => {
    if (!isSignedIn) {
      alert('Please sign in to save items.');
      return;
    }
    try {
      await addToCartMutation.mutateAsync({
        user_id: userId, upc: product.upc,
        product_name: product.product_name, brand_name: product.brand_name,
        added_date: new Date().toISOString(),
      });
      alert('Added to My Groceries!');
    } catch (error) {
      alert('Error adding to list: ' + (error as Error).message);
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
            <ProductCard key={product.upc} product={product} onAddToCart={handleAddToCart} showAddButton={product.verdict !== 'DONT_BUY'} />
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-10">

      {/* Recall alert banner */}
      {alertsData && alertsData.unviewed_count > 0 && (
        <Link to="/groceries"
          className="block rounded-xl border border-black/10 bg-amber-50/80 hover:bg-amber-50 hover:border-amber-200/60 p-4 transition-colors">
          <div className="flex items-start gap-3">
            <Bell className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-[#1A1A1A]">
                {alertsData.unviewed_count} new recall alert{alertsData.unviewed_count > 1 ? 's' : ''}
              </p>
              <p className="text-xs text-[#888] mt-1">
                {alertsData.alerts[0]?.product_name} was recalled — tap to view details
              </p>
              <p className="text-xs text-[#888] mt-2 flex items-center gap-1">
                View alerts <ChevronRight className="w-4 h-4" />
              </p>
            </div>
          </div>
        </Link>
      )}

      {/* Static example if no real alerts */}
      {(!alertsData || alertsData.unviewed_count === 0) && (
        <Link to="/groceries"
          className="block rounded-xl border border-black/10 bg-amber-50/80 hover:bg-amber-50 hover:border-amber-200/60 p-4 transition-colors">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-[#1A1A1A]">
                Stay informed about food recalls
              </p>
              <p className="text-xs text-[#888] mt-1">
                Scan products to check for active recalls, allergens, and diet conflicts.
              </p>
              <p className="text-xs text-[#888] mt-2 flex items-center gap-1">
                View your grocery list <ChevronRight className="w-4 h-4" />
              </p>
            </div>
          </div>
        </Link>
      )}

      <section>
        <h2 className="text-xl font-semibold text-[#1A1A1A] mb-6">Search for a product</h2>
        <ManualInput onSearch={handleSearch} isLoading={searchMutation.isPending} />
        <div className="mt-6">
          <Link to="/scan"
            className="inline-flex items-center gap-2 text-sm font-medium text-[#888] hover:text-[#1A1A1A] transition-colors duration-200">
            <Camera className="w-4 h-4" /> Or scan a barcode with your camera
          </Link>
        </div>
      </section>

      {searchMutation.isPending && (
        <div className="flex justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-[#888]" />
        </div>
      )}

      {renderResults()}

      <section className="pt-8 border-t border-black/10">
        <h3 className="text-sm font-semibold text-[#1A1A1A] mb-4">About food recalls</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
          <div className="py-4 rounded-xl border border-transparent hover:bg-black/[0.02] hover:border-black/5 transition-colors duration-200">
            <p className="text-2xl font-semibold text-[#1A1A1A]">~300</p>
            <p className="text-sm text-[#888] mt-1">Food recalls annually</p>
          </div>
          <div className="py-4 rounded-xl border border-transparent hover:bg-black/[0.02] hover:border-black/5 transition-colors duration-200">
            <p className="text-2xl font-semibold text-[#1A1A1A]">&lt;20%</p>
            <p className="text-sm text-[#888] mt-1">Household awareness rate</p>
          </div>
          <div className="py-4 rounded-xl border border-transparent hover:bg-black/[0.02] hover:border-black/5 transition-colors duration-200">
            <p className="text-2xl font-semibold text-[#1A1A1A]">2024</p>
            <p className="text-sm text-[#888] mt-1">1,400+ illnesses reported</p>
          </div>
        </div>
      </section>

      <section className="pt-8 mt-8 border-t border-black/10 space-y-4">
        <p className="text-xs text-[#888] leading-relaxed">
          This application is an informational tool only. Ingredient matching is based on product databases and AI analysis, and may not be 100% accurate.
        </p>
        <p className="text-xs text-[#888] leading-relaxed">
          Always read product labels carefully, especially if you have food allergies. When in doubt, consult your healthcare provider.
        </p>
      </section>
    </div>
  );
};
