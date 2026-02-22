/**
 * App root: routing, providers, and auth gate.
 *
 * Flow:
 *  1. Not authenticated & hasn't skipped → Onboarding (login / sign-up).
 *  2. Authenticated but profile not completed → ProfileSetup.
 *  3. Otherwise → main app (MVP + V2 routes).
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useStore } from './store';
import { Onboarding } from './Onboarding';
import { ProfileSetup } from './ProfileSetup';
import { Layout } from './Layout';
import { Home } from './Home';
import { Scan } from './Scan';
import { MyGroceries } from './MyGroceries';
import { Settings } from './Settings';
import { V2Home } from './V2Home';
import { V2Scan } from './V2Scan';
import { V2Groceries } from './V2Groceries';
import { V2Allergens } from './V2Allergens';
import { V2Settings } from './V2Settings';
import { V2DemoIntro } from './V2DemoIntro';
import { AllergenDemoCartResults } from './AllergenDemoCartResults';
import { AllergenDemoRecommendations } from './AllergenDemoRecommendations';
import { V2DemoRestrictions } from './V2DemoRestrictions';

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
  const isAuthenticated = useStore((s) => s.isAuthenticated);
  const hasCompletedProfile = useStore((s) => s.hasCompletedProfile);

  // Gate 1: show login / sign-up
  if (!hasSeenOnboarding) {
    return <Onboarding />;
  }

  // Gate 2: authenticated but hasn't set up profile yet → profile setup
  // (skipped users bypass this entirely)
  if (isAuthenticated && !hasCompletedProfile) {
    return (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Layout>
            <ProfileSetup />
          </Layout>
        </BrowserRouter>
      </QueryClientProvider>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            {/* MVP – V1 features */}
            <Route path="/" element={<Home />} />
            <Route path="/scan" element={<Scan />} />
            <Route path="/groceries" element={<MyGroceries />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/profile" element={<ProfileSetup />} />
            {/* V2 – Stretch goal static demo */}
            <Route path="/v2" element={<V2Home />} />
            <Route path="/v2/scan" element={<V2Scan />} />
            <Route path="/v2/groceries" element={<V2Groceries />} />
            <Route path="/v2/allergens" element={<V2Allergens />} />
            <Route path="/v2/settings" element={<V2Settings />} />
            {/* V2: Allergies step-through flow */}
            <Route path="/v2/demo" element={<V2DemoIntro />} />
            <Route path="/v2/demo/cart" element={<AllergenDemoCartResults />} />
            <Route path="/v2/demo/recommendations" element={<AllergenDemoRecommendations />} />
            <Route path="/v2/demo/allergens" element={<V2Allergens />} />
            <Route path="/v2/demo/restrictions" element={<V2DemoRestrictions />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
