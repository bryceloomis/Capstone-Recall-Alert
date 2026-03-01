/**
 * ReceiptScan: capture or upload a receipt photo, send to backend for
 * OCR + product matching, then show ReceiptReviewModal for user confirmation.
 */
import { useState, useRef } from 'react';
import { Receipt, Camera, Upload, Loader2, ImageIcon } from 'lucide-react';
import { scanReceipt, addToCart } from './api';
import { ReceiptReviewModal } from './ReceiptReviewModal';
import { useStore } from './store';
import type { ReceiptScanResult, ReceiptMatchedProduct } from './api';

export const ReceiptScan = () => {
  const userId      = useStore((state) => state.userId);
  const userProfile = useStore((state) => state.userProfile);
  const isSignedIn  = userProfile != null && (userProfile.name != null || userProfile.email != null);

  const [preview, setPreview]   = useState<string | null>(null);
  const [file, setFile]         = useState<File | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [result, setResult]     = useState<ReceiptScanResult | null>(null);
  const [error, setError]       = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [addedCount, setAddedCount] = useState<number | null>(null);

  const cameraInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef   = useRef<HTMLInputElement>(null);

  const handleFileSelected = (selectedFile: File) => {
    setFile(selectedFile);
    setResult(null);
    setError(null);
    setAddedCount(null);
    const url = URL.createObjectURL(selectedFile);
    setPreview(url);
  };

  const handleCameraCapture = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFileSelected(f);
  };

  const handleFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFileSelected(f);
  };

  const handleScan = async () => {
    if (!file) return;
    setIsScanning(true);
    setError(null);
    try {
      const scanResult = await scanReceipt(file);
      setResult(scanResult);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Something went wrong. Please try again.';
      setError(msg);
    } finally {
      setIsScanning(false);
    }
  };

  const handleAddSelected = async (items: ReceiptMatchedProduct[]) => {
    if (!isSignedIn) return;
    setIsAdding(true);
    let added = 0;
    for (const item of items) {
      try {
        await addToCart({
          user_id: userId,
          upc: item.upc || `receipt-${Date.now()}-${added}`,
          product_name: item.product_name,
          brand_name: item.brand_name,
          added_date: new Date().toISOString(),
        });
        added++;
      } catch {
        // Skip items that fail (e.g. already in cart)
      }
    }
    setIsAdding(false);
    setResult(null);
    setAddedCount(added);
    setPreview(null);
    setFile(null);
  };

  const handleReset = () => {
    setPreview(null);
    setFile(null);
    setResult(null);
    setError(null);
    setAddedCount(null);
  };

  return (
    <div className="space-y-6">
      {/* Success confirmation */}
      {addedCount !== null && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-800 flex items-center gap-2">
          <span className="font-medium">✓ Added {addedCount} item{addedCount !== 1 ? 's' : ''} to My Groceries!</span>
          <button onClick={handleReset} className="ml-auto text-xs text-emerald-700 underline underline-offset-2">
            Scan another
          </button>
        </div>
      )}

      {/* Idle / upload area */}
      {!preview && addedCount === null && (
        <div className="bg-white border border-black/5 rounded-2xl p-10 text-center space-y-5">
          <Receipt className="w-12 h-12 text-[#888] mx-auto" />
          <div>
            <p className="text-sm font-medium text-black mb-1">Scan a grocery receipt</p>
            <p className="text-sm text-[#888]">
              We'll read the items, match them to products, and check for recalls.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            {/* Camera capture (mobile) */}
            <button
              onClick={() => cameraInputRef.current?.click()}
              className="flex items-center justify-center gap-2 px-5 py-2.5 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity"
            >
              <Camera className="w-4 h-4" />
              Take photo
            </button>
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={handleCameraCapture}
            />

            {/* File upload (desktop) */}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center justify-center gap-2 px-5 py-2.5 border border-black/10 text-black rounded-xl text-sm font-medium hover:bg-black hover:text-white hover:border-black transition-colors"
            >
              <Upload className="w-4 h-4" />
              Upload image
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleFilePick}
            />
          </div>

          <p className="text-xs text-[#888]">Supports JPG, PNG, HEIC · Best results with clear, well-lit photos</p>
        </div>
      )}

      {/* Preview + scan button */}
      {preview && !isScanning && !result && (
        <div className="space-y-4">
          <div className="bg-white border border-black/5 rounded-2xl overflow-hidden">
            <img
              src={preview}
              alt="Receipt preview"
              className="w-full max-h-80 object-contain p-4"
            />
          </div>

          {error && (
            <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleScan}
              className="flex-1 flex items-center justify-center gap-2 py-3 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity"
            >
              <ImageIcon className="w-4 h-4" />
              Scan this receipt
            </button>
            <button
              onClick={handleReset}
              className="px-4 py-3 border border-black/10 text-black rounded-xl text-sm font-medium hover:bg-black/5 transition-colors"
            >
              Retake
            </button>
          </div>
        </div>
      )}

      {/* Scanning / loading */}
      {isScanning && (
        <div className="bg-white border border-black/5 rounded-2xl p-12 flex flex-col items-center gap-4">
          <Loader2 className="w-10 h-10 animate-spin text-[#888]" />
          <div className="text-center">
            <p className="text-sm font-medium text-black">Reading your receipt…</p>
            <p className="text-xs text-[#888] mt-1">OCR + product matching can take 5–15 seconds</p>
          </div>
        </div>
      )}

      {/* Review modal */}
      {result && (
        <ReceiptReviewModal
          result={result}
          isSignedIn={isSignedIn}
          isAdding={isAdding}
          onAddSelected={handleAddSelected}
          onClose={() => setResult(null)}
        />
      )}
    </div>
  );
};
