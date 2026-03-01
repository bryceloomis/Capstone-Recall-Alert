/**
 * MVP Home: search by UPC or name (ManualInput), link to Scan, then show ProductCard(s) and add-to-cart.
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Camera, Loader2, AlertCircle, ChevronRight } from 'lucide-react';
import { ManualInput } from './ManualInput';
import { ProductCard } from './ProductCard';
import { useSearchProduct, useAddToCart } from './useProduct';
import { useStore } from './store';
import type { Product } from './types';

/** Example recall notification (links to My Groceries where full recall details are shown). */
const EXAMPLE_RECALL_NOTIFICATION = {
  product_name: 'Classic granola',
  brand_name: 'Brand B',
  recall_date: '2025-01-15',
  reason: 'Potential contamination with undeclared tree nuts. Check label and manufacturer for details.',
};

export const Home = () => {
  const [results, setResults] = useState<Product | Product[] | null>(null);
  const searchMutation    = useSearchProduct();
  const addToCartMutation = useAddToCart();
  const userId            = useStore((state) => state.userId);
  const userProfile       = useStore((state) => state.userProfile);
  const isSignedIn        = userProfile != null && (userProfile.name != null || userProfile.email != null);

  const handleSearch = async (query: string, type: 'upc' | 'name') => {
    try {
      const result = await searchMutation.mutateAsync(
        type === 'upc' ? { upc: query } : { name: query }
      );
      setResults(result);
    } catch (error) {
      alert('Error: ' + (error as Error).message);
      setResults(null);
    }
  };

  const handleAddToCart = async (product: Product) => {
    if (!isSignedIn) {
      alert('Please sign in or create an account to save items to your grocery list.');
      return;
    }
    try {
      await addToCartMutation.mutateAsync({
        user_id: userId,
        upc: product.upc,
        product_name: product.product_name,
        brand_name: product.brand_name,
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
            <ProductCard
              key={product.upc}
              product={product}
              onAddToCart={handleAddToCart}
              showAddButton={!product.is_recalled}
            />
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-10">
      <Link
        to="/groceries"
        className="block rounded-xl border border-black/10 bg-amber-50/80 hover:bg-amber-50 hover:border-amber-200/60 p-4 transition-colors"
      >
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-[#1A1A1A]">
              One of your previously scanned products was just recalled
            </p>
            <p className="text-sm text-[#888] mt-1">
              <span className="font-medium text-[#1A1A1A]">{EXAMPLE_RECALL_NOTIFICATION.product_name}</span>
              {' · '}
              {EXAMPLE_RECALL_NOTIFICATION.brand_name}
            </p>
            <p className="text-xs text-[#888] mt-1 line-clamp-2">
              {EXAMPLE_RECALL_NOTIFICATION.reason}
            </p>
            <p className="text-xs text-[#888] mt-2 flex items-center gap-1">
              View full recall details
              <ChevronRight className="w-4 h-4" />
            </p>
          </div>
        </div>
      </Link>

      <section>
        <h2 className="text-xl font-semibold text-[#1A1A1A] mb-6">Search for a product</h2>
        <ManualInput
          onSearch={handleSearch}
          isLoading={searchMutation.isPending}
        />
        <div className="mt-6">
          <Link
            to="/scan"
            className="inline-flex items-center gap-2 text-sm font-medium text-[#888] hover:text-[#1A1A1A] transition-colors duration-200"
          >
            <Camera className="w-4 h-4" />
            Or scan a barcode with your camera
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
          This application is an informational tool only and does not provide medical advice. Ingredient matching is based on product databases and may not be 100% accurate or complete.
        </p>
        <p className="text-xs text-[#888] leading-relaxed">
          Always read product labels carefully, especially if you have food allergies or medical dietary restrictions. When in doubt, consult healthcare providers or contact manufacturers directly.
        </p>
        <p className="text-xs text-[#888] leading-relaxed">
          By using this app, you acknowledge that you are responsible for your own food safety decisions.
        </p>
      </section>
    </div>
  );
};
