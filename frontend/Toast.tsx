import { useEffect, useState, useCallback, useSyncExternalStore } from 'react';
import { CheckCircle, AlertCircle, X } from 'lucide-react';

type ToastType = 'success' | 'error';

interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
}

let toasts: ToastItem[] = [];
let nextId = 0;
const listeners = new Set<() => void>();
function emit() { listeners.forEach((l) => l()); }

export function toast(message: string, type: ToastType = 'success') {
  const id = nextId++;
  toasts = [...toasts, { id, message, type }];
  emit();
  setTimeout(() => dismiss(id), 3500);
}
toast.success = (msg: string) => toast(msg, 'success');
toast.error = (msg: string) => toast(msg, 'error');

function dismiss(id: number) {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

function useToasts() {
  return useSyncExternalStore(
    (cb) => { listeners.add(cb); return () => listeners.delete(cb); },
    () => toasts,
  );
}

function ToastEntry({ item, onDismiss }: { item: ToastItem; onDismiss: () => void }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
    const timer = setTimeout(() => setVisible(false), 3000);
    return () => clearTimeout(timer);
  }, []);

  const Icon = item.type === 'success' ? CheckCircle : AlertCircle;

  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 rounded-2xl shadow-lg shadow-black/10 backdrop-blur-xl border max-w-sm w-full transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-3'
      } ${
        item.type === 'success'
          ? 'bg-white/95 border-black/[0.06] text-[#1A1A1A]'
          : 'bg-red-50/95 border-red-200/50 text-red-900'
      }`}
    >
      <Icon className={`w-[18px] h-[18px] shrink-0 ${
        item.type === 'success' ? 'text-emerald-500' : 'text-red-500'
      }`} />
      <p className="text-sm font-medium flex-1">{item.message}</p>
      <button
        type="button"
        onClick={onDismiss}
        className="shrink-0 text-black/20 hover:text-black/50 transition-colors"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

export function Toaster() {
  const items = useToasts();

  if (items.length === 0) return null;

  return (
    <div className="fixed top-5 left-1/2 -translate-x-1/2 z-[9999] flex flex-col items-center gap-2 pointer-events-none">
      {items.map((item) => (
        <div key={item.id} className="pointer-events-auto">
          <ToastEntry item={item} onDismiss={() => dismiss(item.id)} />
        </div>
      ))}
    </div>
  );
}
