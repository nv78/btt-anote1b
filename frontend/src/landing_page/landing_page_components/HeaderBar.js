import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  loginPath,
  mySubmissionsPath,
  submittoleaderboardPath,
} from '../../constants/RouteConstants';
import { canAccessContributorRoutes, clearLeaderboardJwt, getLeaderboardJwt } from '../../utils/leaderboardAuth';

export default function HeaderBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [authRev, setAuthRev] = useState(0);

  useEffect(() => {
    setAuthRev((r) => r + 1);
  }, [location.pathname]);

  const navItems = [
    { label: 'Leaderboard', path: '/' },
    { label: 'Submit', path: submittoleaderboardPath },
    { label: 'My submissions', path: mySubmissionsPath },
  ];

  const signedInWithJwt = authRev >= 0 && !!getLeaderboardJwt();
  const canPassContributorGate = authRev >= 0 && canAccessContributorRoutes();

  const onSignOut = () => {
    clearLeaderboardJwt();
    setAuthRev((r) => r + 1);
    navigate('/');
  };

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/' || location.pathname === '';
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  return (
    <div className="sticky top-0 z-50 bg-[#080d16]/96 backdrop-blur-lg border-b border-white/[0.05]">
      <div className="max-w-7xl mx-auto px-4">
        <div className="h-14 flex items-center justify-between">
          {/* Logo */}
          <button
            type="button"
            onClick={() => navigate('/')}
            className="flex items-center gap-2.5 shrink-0"
            aria-label="Go to leaderboard home"
          >
            <img src="/logo.png" alt="Anote" className="h-7 w-7" />
              <a
              href="https://anote.ai"
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 px-3 py-1.5 rounded-lg font-medium  hover:bg-[#28b2fb]/[0.08] transition-all duration-150"
            >
                          <span className="font-bold text-white">
              Anote
                          </span>
            </a>
          </button>

          {/* Desktop nav */}
          <nav className="hidden sm:flex items-center gap-0.5">
            {navItems.map((item) => (
              <button
                key={item.path}
                type="button"
                onClick={() => navigate(item.path)}
                className={[
                  "px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-150",
                  item.outlined ? "ml-1 border border-[#28b2fb]/30" : "",
                  isActive(item.path)
                    ? item.outlined
                      ? "text-[#defe47] border-[#defe47]/50 bg-[#defe47]/5 font-semibold"
                      : "text-[#defe47] font-semibold"
                    : item.outlined
                      ? "text-[#28b2fb] hover:text-[#defe47] hover:border-[#defe47]/40 hover:bg-[#defe47]/5"
                      : "text-gray-400 hover:text-gray-100"
                ].join(' ')}
              >
                {item.label}
              </button>
            ))}
            {canPassContributorGate ? (
              signedInWithJwt ? (
                <button
                  type="button"
                  onClick={onSignOut}
                  className="ml-1 px-3 py-1.5 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/[0.06] transition-all"
                >
                  Sign out
                </button>
              ) : null
            ) : (
              <button
                type="button"
                onClick={() => navigate(loginPath)}
                className="ml-1 px-3 py-1.5 rounded-lg text-sm font-medium text-[#defe47] border border-[#defe47]/40 hover:bg-[#defe47]/10 transition-all"
              >
                Log in
              </button>
            )}
            {/* <a
              href="https://anote.ai"
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 px-3 py-1.5 rounded-lg text-sm font-medium text-[#28b2fb] border border-[#28b2fb]/20 hover:bg-[#28b2fb]/[0.08] transition-all duration-150"
            >
              Anote.ai ↗
            </a> */}
          </nav>

          {/* Mobile hamburger */}
          <button
            type="button"
            className="sm:hidden p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/[0.06] transition-colors"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle navigation"
          >
            {mobileOpen ? (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>

        {/* Mobile nav dropdown */}
        {mobileOpen && (
          <div className="sm:hidden pb-3 flex flex-col gap-0.5 border-t border-white/[0.05] pt-2">
            {navItems.map((item) => (
              <button
                key={item.path}
                type="button"
                onClick={() => { navigate(item.path); setMobileOpen(false); }}
                className={[
                  "px-3 py-2 rounded-lg text-sm font-medium text-left transition-all",
                  item.outlined ? "border border-[#28b2fb]/30" : "",
                  isActive(item.path)
                    ? item.outlined
                      ? "bg-[#defe47]/10 text-[#defe47] border-[#defe47]/50 font-semibold"
                      : "bg-[#defe47] text-black font-semibold"
                    : item.outlined
                      ? "text-[#28b2fb] hover:text-[#defe47] hover:border-[#defe47]/40 hover:bg-[#defe47]/5"
                      : "text-gray-400 hover:text-gray-100 hover:bg-white/[0.06]"
                ].join(' ')}
              >
                {item.label}
              </button>
            ))}
            {canPassContributorGate ? (
              signedInWithJwt ? (
                <button
                  type="button"
                  onClick={() => { onSignOut(); setMobileOpen(false); }}
                  className="px-3 py-2 rounded-lg text-sm font-medium text-left text-gray-400 hover:text-white hover:bg-white/[0.06]"
                >
                  Sign out
                </button>
              ) : null
            ) : (
              <button
                type="button"
                onClick={() => { navigate(loginPath); setMobileOpen(false); }}
                className="px-3 py-2 rounded-lg text-sm font-medium text-left bg-[#defe47]/10 text-[#defe47] border border-[#defe47]/30"
              >
                Log in
              </button>
            )}
            {/* <a
              href="https://anote.ai"
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-2 rounded-lg text-sm font-medium text-[#28b2fb] hover:bg-[#28b2fb]/[0.08] transition-all"
            >
              Anote.ai ↗
            </a> */}
          </div>
        )}
      </div>
    </div>
  );
}
