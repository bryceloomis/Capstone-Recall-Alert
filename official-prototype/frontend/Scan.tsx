/**
 * MVP Scan: open BarcodeScanner (ZXing), then lookup via searchProduct (checkRecallByUPC) and show ProductCard.
 */
import { useState } from 'react';
import { Camera } from 'lucide-react';
import { BarcodeScanner } from './BarcodeScanner';
import { ProductCard } from './ProductCard';
import { useSearchProduct, useAddToCart } from './useProduct';
import { useStore } from './store';
import type { Product } from './types';

export const Scan = () => {
  const [showScanner, setShowScanner] = useState(false);
  const [scannedProduct, setScannedProduct] = useState<Product | null>(null);
  const searchMutation = useSearchProduct();
  const addToCartMutation = useAddToCart();
  const userId = useStore((state) => state.userId);

  const handleScan = async (barcode: string) => {
    setShowScanner(false);
    try {
      const result = await searchMutation.mutateAsync({ upc: barcode });
      if (!Array.isArray(result)) setScannedProduct(result);
    } catch {
      alert('Could not load product. Try again or search by name on Home.');
      setScannedProduct(null);
    }
  };

  const handleAddToCart = async (product: Product) => {
    try {
      await addToCartMutation.mutateAsync({
        user_id: userId,
        upc: product.upc,
        product_name: product.product_name,
        brand_name: product.brand_name,
        added_date: new Date().toISOString(),
      });
      alert('Added to My Groceries.');
    } catch {
      alert('Error adding to cart');
    }
  };

  const handleScanAgain = () => {
    setScannedProduct(null);
    setShowScanner(true);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <h2 className="text-xl font-semibold text-black">Scan barcode</h2>

      {!scannedProduct && (
        <div className="space-y-6">
          <div className="bg-white border border-black/5 rounded-2xl p-12 text-center">
            <Camera className="w-14 h-14 text-[#888] mx-auto mb-4" />
            <p className="text-[#888] text-sm mb-6">
              Position the barcode within the camera view.
            </p>
            <button
              onClick={() => setShowScanner(true)}
              className="inline-flex items-center gap-2 px-6 py-3 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity"
            >
              <Camera className="w-5 h-5" />
              Start camera
            </button>
          </div>
          <p className="text-[#888] text-sm">
            Camera access via browser. Supports UPC-A, EAN-13, Code 128.
          </p>
        </div>
      )}

      {scannedProduct && (
        <div className="space-y-6">
          <div className="rounded-xl border border-black/5 bg-white px-4 py-3">
            <p className="text-sm font-medium text-black">
              Barcode: {scannedProduct.upc}
            </p>
          </div>
          <ProductCard
            product={scannedProduct}
            onAddToCart={handleAddToCart}
            showAddButton={!scannedProduct.is_recalled}
          />
          <button
            onClick={handleScanAgain}
            className="w-full px-6 py-3 bg-black/5 text-black rounded-xl text-sm font-medium hover:bg-black/10 transition-colors"
          >
            Scan another
          </button>
        </div>
      )}

      {showScanner && (
        <BarcodeScanner
          onScan={handleScan}
          onClose={() => setShowScanner(false)}
        />
      )}
    </div>
  );
};
