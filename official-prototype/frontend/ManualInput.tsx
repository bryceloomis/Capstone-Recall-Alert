/**
 * Home search: UPC input + product-name input; calls onSearch(query, 'upc' | 'name').
 */
import { useState } from 'react';
import { Search } from 'lucide-react';

interface ManualInputProps {
  onSearch: (query: string, type: 'upc' | 'name') => void;
  isLoading?: boolean;
}

export const ManualInput = ({ onSearch, isLoading = false }: ManualInputProps) => {
  const [upcValue, setUpcValue] = useState('');
  const [nameValue, setNameValue] = useState('');

  const handleUpcSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (upcValue.trim()) onSearch(upcValue.trim(), 'upc');
  };

  const handleNameSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (nameValue.trim()) onSearch(nameValue.trim(), 'name');
  };

  const inputClass = "flex-1 px-4 py-3 bg-transparent border border-black/5 rounded-xl text-[#1A1A1A] placeholder-[#888] focus:outline-none focus:border-black/15 hover:border-black/10 transition-colors duration-200";
  const btnClass = "px-5 py-3 rounded-xl text-sm font-medium text-[#1A1A1A] border border-black/10 hover:bg-[#1A1A1A] hover:text-white hover:border-[#1A1A1A] disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-[#1A1A1A] transition-colors duration-200 flex items-center gap-2 shrink-0";

  return (
    <div className="space-y-6">
      <div>
        <label htmlFor="upc-input" className="block text-sm font-medium text-black mb-2">
          Enter UPC barcode
        </label>
        <form onSubmit={handleUpcSearch} className="flex gap-2">
          <input
            type="text"
            id="upc-input"
            value={upcValue}
            onChange={(e) => setUpcValue(e.target.value)}
            placeholder="e.g. 041190468831"
            className={inputClass}
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading || !upcValue.trim()} className={btnClass}>
            <Search className="w-4 h-4" />
            Search
          </button>
        </form>
      </div>

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-black/10" />
        </div>
        <div className="relative flex justify-center">
            <span className="px-4 bg-cream text-[#888] text-sm font-medium">or</span>
          </div>
      </div>

      <div>
        <label htmlFor="name-input" className="block text-sm font-medium text-black mb-2">
          Search by product name
        </label>
        <form onSubmit={handleNameSearch} className="flex gap-2">
          <input
            type="text"
            id="name-input"
            value={nameValue}
            onChange={(e) => setNameValue(e.target.value)}
            placeholder="e.g. granola"
            className={inputClass}
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading || !nameValue.trim()} className={btnClass}>
            <Search className="w-4 h-4" />
            Search
          </button>
        </form>
      </div>
    </div>
  );
};
