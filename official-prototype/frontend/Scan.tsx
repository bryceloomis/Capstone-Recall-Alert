/**
 * MVP Scan: open BarcodeScanner (ZXing), look up via Open Food Facts + recall DB in
 * parallel, then show ScanResultModal with product info + recall status.
 */
import { useState } from 'react';
import { Camera, Loader2 } from 'lucide-react';
import { BarcodeScanner } from './BarcodeScanner';
import { ScanResultModal } from './ScanResultModal';
import { lookupByUPC } from './api';
import { useAddToCart } from './useProduct';
import { useStore } from './store';
import type { Product } from './types';

export const Scan = () => {
  const [showScanner, setShowScanner]       = useState(false);
  const [isLooking, setIsLooking]           = useState(false);
  const [scannedProduct, setScannedProduct] = useState<Product | null>(null);

  const addToCartMutation = useAddToCart();
  const userId            = useStore((state) => state.userId);
  const userProfile       = useStore((state) => state.userProfile);
  const isSignedIn        = userProfile != null && (userProfile.name != null || userProfile.email != null);

  const handleScan = async (barcode: string) => {
    setShowScanner(false);
    setIsLooking(true);
    try {
      const product = await lookupByUPC(barcode);
      setScannedProduct(product);
    } catch {
      alert('Could not look up product. Try again or search by name on Home.');
    } finally {
      setIsLooking(false);
    }
  };

  const handleAddToCart = async (product: Product) => {
    if (!isSignedIn) return;
    try {
      await addToCartMutation.mutateAsync({
        user_id: userId,
        upc: product.upc,
        product_name: product.product_name,
        brand_name: product.brand_name,
        added_date: new Date().toISOString(),
      });
      alert('Added to My Groceries!');
    } catch {
      alert('Error adding to list — please try again.');
    }
  };

  const handleScanAgain = () => {
    setScannedProduct(null);
    setShowScanner(true);
  };

  const handleClose = () => {
    setScannedProduct(null);
    setShowScanner(false);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <h2 className="text-xl font-semibold text-black">Scan barcode</h2>

      {/* Idle state */}
      {!scannedProduct && !isLooking && (
        <div className="space-y-6">
          <div className="bg-white border border-black/5 rounded-2xl p-12 text-center">
            <Camera className="w-14 h-14 text-[#888] mx-auto mb-4" />
            <p className="text-[#888] text-sm mb-6">
              Point your camera at a product barcode. We'll check it against the recall
              database and show you product details.
            </p>
            <button
              onClick={() => setShowScanner(true)}
              className="inline-flex items-center gap-2 px-6 py-3 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity"
            >
              <Camera className="w-5 h-5" />
              Start camera
            </button>
          </div>
          <p className="text-[#888] text-sm text-center">
            Supports UPC-A, EAN-13, Code 128
          </p>
        </div>
      )}

      {/* Looking up product */}
      {isLooking && (
        <div className="bg-white border border-black/5 rounded-2xl p-12 flex flex-col items-center gap-4">
          <Loader2 className="w-10 h-10 animate-spin text-[#888]" />
          <p className="text-sm text-[#888]">Checking recall database…</p>
        </div>
      )}

      {/* Camera overlay */}
      {showScanner && (
        <BarcodeScanner
          onScan={handleScan}
          onClose={() => setShowScanner(false)}
        />
      )}

      {/* Result modal — full-screen overlay */}
      {scannedProduct && (
        <ScanResultModal
          product={scannedProduct}
          isSignedIn={isSignedIn}
          onAddToCart={handleAddToCart}
          onScanAgain={handleScanAgain}
          onClose={handleClose}
          isAdding={addToCartMutation.isPending}
        />
      )}
    </div>
  );
};
