/**
 * MVP Scan: two tabs — "Barcode" (camera + ZXing) and "Receipt" (photo OCR).
 * Barcode: looks up via Open Food Facts + recall DB in parallel, shows ScanResultModal.
 * Receipt: uploads photo to backend for Textract OCR + OFF matching, shows ReceiptReviewModal.
 */
import { useState } from 'react';
import { Camera, Receipt, Loader2 } from 'lucide-react';
import { BarcodeScanner } from './BarcodeScanner';
import { ScanResultModal } from './ScanResultModal';
import { ReceiptScan } from './ReceiptScan';
import { lookupByUPC } from './api';
import { useAddToCart } from './useProduct';
import { useStore } from './store';
import type { Product } from './types';

type Tab = 'barcode' | 'receipt';

export const Scan = () => {
  const [activeTab, setActiveTab]           = useState<Tab>('barcode');
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
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-xl font-semibold text-black">Scan</h2>

      {/* Tab switcher */}
      <div className="flex rounded-xl border border-black/10 p-1 bg-white">
        <button
          type="button"
          onClick={() => setActiveTab('barcode')}
          className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-colors duration-200 ${
            activeTab === 'barcode'
              ? 'bg-[#1A1A1A] text-white'
              : 'text-[#888] hover:text-[#1A1A1A]'
          }`}
        >
          <Camera className="w-4 h-4" />
          Barcode
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('receipt')}
          className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-colors duration-200 ${
            activeTab === 'receipt'
              ? 'bg-[#1A1A1A] text-white'
              : 'text-[#888] hover:text-[#1A1A1A]'
          }`}
        >
          <Receipt className="w-4 h-4" />
          Receipt
        </button>
      </div>

      {/* ── Barcode tab ─────────────────────────────────────────────────────── */}
      {activeTab === 'barcode' && (
        <>
          {/* Idle */}
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

          {/* Looking up */}
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

          {/* Result modal */}
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
        </>
      )}

      {/* ── Receipt tab ─────────────────────────────────────────────────────── */}
      {activeTab === 'receipt' && <ReceiptScan />}
    </div>
  );
};
