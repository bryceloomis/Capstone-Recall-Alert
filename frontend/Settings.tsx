/**
 * MVP Settings: Account info, notification toggles, privacy copy, and sign-out at bottom.
 */
import { useState } from 'react';
import { User, Bell, Shield, Info, LogOut } from 'lucide-react';
import { useStore } from './store';

export const Settings = () => {
  const userId = useStore((state) => state.userId);
  const setUserId = useStore((state) => state.setUserId);
  const hasSeenOnboarding = useStore((state) => state.hasSeenOnboarding);
  const setHasSeenOnboarding = useStore((state) => state.setHasSeenOnboarding);
  const userProfile = useStore((state) => state.userProfile);
  const setUserProfile = useStore((state) => state.setUserProfile);

  const isSignedIn = userProfile != null && (userProfile.name != null || userProfile.email != null);

  const [localUserId, setLocalUserId] = useState(userId);
  const [notifications, setNotifications] = useState({
    inApp: true,
    push: false,
    urgencyThreshold: 'all' as 'all' | 'class1_only',
  });

  const handleSaveUserId = () => {
    setUserId(localUserId);
    alert('User ID updated.');
  };

  const handleBackToSignIn = () => {
    setHasSeenOnboarding(false);
  };

  const handleSignOut = () => {
    setUserProfile({ name: undefined, email: undefined });
    setUserId('test_user');
    setHasSeenOnboarding(false);
  };

  const sectionClass = "mb-8 border border-black/5 rounded-xl p-6 bg-white";
  const headingClass = "flex items-center gap-3 mb-4";
  const iconClass = "w-5 h-5 text-[#888]";
  const labelClass = "block text-sm font-medium text-black mb-2";
  const inputClass = "flex-1 px-4 py-2.5 bg-cream border border-black/10 rounded-xl text-black focus:outline-none focus:border-black/20";
  const btnClass = "px-5 py-2.5 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity";

  return (
    <div className="max-w-2xl mx-auto space-y-2">
      <h2 className="text-xl font-semibold text-black mb-6">Settings</h2>

      <section className={sectionClass}>
        <div className={headingClass}>
          <User className={iconClass} />
          <h3 className="text-lg font-semibold text-black">Account</h3>
        </div>
        {isSignedIn ? (
          <div className="space-y-3">
            <div>
              <p className="text-xs text-[#888] mb-0.5">Name</p>
              <p className="text-sm font-medium text-black">{userProfile!.name ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-[#888] mb-0.5">Email</p>
              <p className="text-sm font-medium text-black">{userProfile!.email ?? '—'}</p>
            </div>
          </div>
        ) : (
          <div>
            <label className={labelClass}>User ID</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={localUserId}
                onChange={(e) => setLocalUserId(e.target.value)}
                className={inputClass}
              />
              <button onClick={handleSaveUserId} className={btnClass}>
                Save
              </button>
            </div>
          </div>
        )}
      </section>

      <section className={sectionClass}>
        <div className={headingClass}>
          <Bell className={iconClass} />
          <h3 className="text-lg font-semibold text-black">Notifications</h3>
        </div>
        <div className="space-y-4">
          <label className="flex items-center justify-between">
            <span className="text-black text-sm">In-app notifications</span>
            <input
              type="checkbox"
              checked={notifications.inApp}
              onChange={(e) => setNotifications({ ...notifications, inApp: e.target.checked })}
              className="w-4 h-4 rounded border-black/20 text-black focus:ring-black/20"
            />
          </label>
          <label className="flex items-center justify-between">
            <span className="text-black text-sm">Browser push notifications</span>
            <input
              type="checkbox"
              checked={notifications.push}
              onChange={(e) => setNotifications({ ...notifications, push: e.target.checked })}
              className="w-4 h-4 rounded border-black/20 text-black focus:ring-black/20"
            />
          </label>
          <div>
            <label className={labelClass}>Urgency threshold</label>
            <select
              value={notifications.urgencyThreshold}
              onChange={(e) =>
                setNotifications({
                  ...notifications,
                  urgencyThreshold: e.target.value as 'all' | 'class1_only',
                })
              }
              className="w-full px-4 py-2.5 bg-cream border border-black/10 rounded-xl text-black focus:outline-none focus:border-black/20"
            >
              <option value="all">All recalls</option>
              <option value="class1_only">Class I only (most serious)</option>
            </select>
          </div>
        </div>
      </section>

      <section className={sectionClass}>
        <div className={headingClass}>
          <Shield className={iconClass} />
          <h3 className="text-lg font-semibold text-black">Privacy & data</h3>
        </div>
        <div className="space-y-2 text-sm text-[#888]">
          <p>Your list is stored locally on this device by default.</p>
          <p>We only check stored products against the recall database; no personal data is shared.</p>
        </div>
      </section>

      <section className={sectionClass}>
        <div className={headingClass}>
          <Info className={iconClass} />
          <h3 className="text-lg font-semibold text-black">About</h3>
        </div>
        <div className="space-y-2 text-sm text-[#888]">
          <p><span className="font-medium text-black">Version:</span> 1.0.0</p>
          <p><span className="font-medium text-black">Project:</span> UC Berkeley MIDS Capstone</p>
          <p><span className="font-medium text-black">Data sources:</span> FDA & USDA Recall APIs</p>
        </div>
      </section>

      {/* Sign out / sign in — bottom of page */}
      <section className={sectionClass}>
        {isSignedIn ? (
          <button
            onClick={handleSignOut}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 border border-black/10 text-black rounded-xl text-sm font-medium hover:bg-black hover:text-white hover:border-black transition-colors duration-200"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        ) : (
          <div className="text-center space-y-2">
            <button
              onClick={handleBackToSignIn}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-black text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity"
            >
              Sign in or create account
            </button>
            <p className="text-xs text-[#888]">Return to the sign-in page.</p>
          </div>
        )}
      </section>
    </div>
  );
};
