/**
 * Shell around all pages: TopNav, main content area, MVP-only sidebar & bottom nav, footer.
 * V2 pages (/v2*) get no sidebar or bottom nav.
 */
import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, Camera, ShoppingCart, Settings } from 'lucide-react';
import { TopNav } from './TopNav';

interface LayoutProps {
  children: ReactNode;
}

export const Layout = ({ children }: LayoutProps) => {
  const location = useLocation();
  const isV2 = location.pathname.startsWith('/v2'); // V2 uses step nav in TopNav only; no sidebar/bottom nav

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="min-h-screen bg-cream">
      <TopNav />

      <main className={`max-w-4xl mx-auto px-4 py-8 pb-28 md:pb-12 ${!isV2 ? 'md:pl-48' : ''}`}>
        {children}
      </main>

      {/* Bottom nav: only for MVP */}
      {!isV2 && (
        <nav className="fixed bottom-0 left-0 right-0 bg-black safe-area-bottom md:hidden">
          <div className="flex justify-around items-center h-14">
            <Link to="/" className={`flex flex-col items-center justify-center flex-1 h-full gap-0.5 transition-colors duration-200 ${isActive('/') ? 'text-white' : 'text-white/50 hover:text-white'}`}>
              <Home className="w-5 h-5" strokeWidth={isActive('/') ? 2.5 : 2} />
              <span className="text-xs font-medium">Home</span>
            </Link>
            <Link to="/scan" className={`flex flex-col items-center justify-center flex-1 h-full gap-0.5 transition-colors duration-200 ${isActive('/scan') ? 'text-white' : 'text-white/50 hover:text-white'}`}>
              <Camera className="w-5 h-5" strokeWidth={isActive('/scan') ? 2.5 : 2} />
              <span className="text-xs font-medium">Scan</span>
            </Link>
            <Link to="/groceries" className={`flex flex-col items-center justify-center flex-1 h-full gap-0.5 transition-colors duration-200 ${isActive('/groceries') ? 'text-white' : 'text-white/50 hover:text-white'}`}>
              <ShoppingCart className="w-5 h-5" strokeWidth={isActive('/groceries') ? 2.5 : 2} />
              <span className="text-xs font-medium">My List</span>
            </Link>
            <Link to="/settings" className={`flex flex-col items-center justify-center flex-1 h-full gap-0.5 transition-colors duration-200 ${isActive('/settings') ? 'text-white' : 'text-white/50 hover:text-white'}`}>
              <Settings className="w-5 h-5" strokeWidth={isActive('/settings') ? 2.5 : 2} />
              <span className="text-xs font-medium">Settings</span>
            </Link>
          </div>
        </nav>
      )}

      {/* Desktop sidebar: only for MVP */}
      {!isV2 && (
        <nav className="hidden md:block fixed top-24 left-8 z-10">
          <div className="flex flex-col gap-0.5">
            {[
              { path: '/', label: 'Home', Icon: Home },
              { path: '/scan', label: 'Scan', Icon: Camera },
              { path: '/groceries', label: 'My Groceries', Icon: ShoppingCart },
              { path: '/settings', label: 'Settings', Icon: Settings },
            ].map(({ path, label, Icon }) => (
              <Link
                key={path}
                to={path}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-full text-sm font-medium transition-colors duration-200 border border-transparent ${
                  isActive(path) ? 'bg-[#1A1A1A] text-white border-[#1A1A1A]' : 'text-[#888] hover:text-[#1A1A1A] hover:bg-black/[0.04] hover:border-black/5'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            ))}
          </div>
        </nav>
      )}

      <footer className="bg-black text-white py-4 pb-24 md:pb-4">
        <div className="max-w-4xl mx-auto px-4 text-center text-sm text-white/80">
          <p>UC Berkeley MIDS Capstone</p>
          <p className="mt-0.5 text-white/60">Data: FDA & USDA Recall APIs</p>
        </div>
      </footer>
    </div>
  );
}
