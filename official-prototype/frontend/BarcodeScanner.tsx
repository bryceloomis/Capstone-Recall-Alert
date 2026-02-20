/**
 * Full-screen camera scanner using ZXing; on successful decode calls onScan(barcode) then closes.
 */
import { Camera, X } from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import { BrowserMultiFormatReader } from '@zxing/browser';
import type { IScannerControls } from '@zxing/browser';

interface BarcodeScannerProps {
  onScan: (barcode: string) => void;
  onClose: () => void;
}

export const BarcodeScanner = ({ onScan, onClose }: BarcodeScannerProps) => {
  const [hasCamera, setHasCamera] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const controlsRef = useRef<IScannerControls | null>(null);

  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setHasCamera(false);
    }
  }, []);

  const stopScanning = () => {
    if (controlsRef.current) {
      try {
        controlsRef.current.stop();
      } catch {
        // ignore
      }
      controlsRef.current = null;
    }
    setIsScanning(false);
  };

  useEffect(() => {
    return () => {
      stopScanning();
    };
  }, []);

  const startCamera = async () => {
    const video = videoRef.current;
    if (!video) return;
    setError(null);
    try {
      const codeReader = new BrowserMultiFormatReader();
      controlsRef.current = await codeReader.decodeFromVideoDevice(
        undefined,
        video,
        (result, err, controls) => {
          if (result) {
            const text = result.getText();
            if (text?.trim()) {
              stopScanning();
              onScan(text.trim());
            }
          }
          if (err && !err.message?.toLowerCase().includes('no barcode')) {
            setError(err.message || 'Scan error');
          }
        }
      );
      setIsScanning(true);
    } catch (e) {
      setHasCamera(false);
      setError(e instanceof Error ? e.message : 'Camera unavailable');
    }
  };

  const handleClose = () => {
    stopScanning();
    onClose();
  };

  if (!hasCamera) {
    return (
      <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
        <div className="bg-white rounded-2xl p-6 max-w-sm w-full">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold text-black">Camera unavailable</h3>
            <button onClick={handleClose} className="text-neutral-400 hover:text-black">
              <X className="w-5 h-5" />
            </button>
          </div>
          <p className="text-neutral-600 text-sm mb-6">
            Camera access is not available. Use manual UPC entry instead.
          </p>
          <button
            onClick={handleClose}
            className="w-full px-4 py-3 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90"
          >
            OK
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black flex flex-col z-50">
      <div className="p-4 flex justify-between items-center border-b border-neutral-800">
        <h3 className="text-white text-base font-semibold">Scan barcode</h3>
        <button onClick={handleClose} className="text-neutral-400 hover:text-white">
          <X className="w-5 h-5" />
        </button>
      </div>
      <div className="flex-1 flex flex-col items-center justify-center min-h-0">
        {isScanning ? (
          <video ref={videoRef} autoPlay playsInline muted className="max-w-full max-h-full object-contain" />
        ) : (
          <div className="text-center">
            <Camera className="w-14 h-14 text-neutral-500 mx-auto mb-4" />
            <p className="text-neutral-400 text-sm mb-4">Ready to scan</p>
            {error && <p className="text-amber-400 text-sm mb-2">{error}</p>}
            <button
              onClick={startCamera}
              className="px-6 py-3 bg-white text-black rounded-xl text-sm font-medium hover:opacity-90"
            >
              Start camera
            </button>
          </div>
        )}
      </div>
      <div className="p-4 border-t border-neutral-800 text-center">
        <p className="text-neutral-500 text-sm">
          {isScanning ? 'Position barcode within the frame.' : 'Supports UPC-A, EAN-13, Code 128.'}
        </p>
      </div>
    </div>
  );
};
