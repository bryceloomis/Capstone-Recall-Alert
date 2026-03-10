/**
 * App root: routing and providers.
 * Shows Onboarding until user has "seen" it (try it out / create account).
 */
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useStore } from './store';
import { Onboarding } from './Onboarding';
import { Layout } from './Layout';
import { Home } from './Home';
import { MyGroceries } from './MyGroceries';

const Scan = lazy(() => import('./Scan').then(m => ({ default: m.Scan })));
import { MyGroceriesExample } from './MyGroceriesExample';
import { Settings } from './Settings';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  const hasSeenOnboarding = useStore((s) => s.hasSeenOnboarding);

  if (!hasSeenOnboarding) {
    return <Onboarding />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/scan" element={<Suspense fallback={<div className="p-4 text-center">Loading…</div>}><Scan /></Suspense>} />
            <Route path="/groceries" element={<MyGroceries />} />
            <Route path="/groceries-example" element={<MyGroceriesExample />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
