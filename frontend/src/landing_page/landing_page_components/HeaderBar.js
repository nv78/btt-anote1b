import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { addDatasetPath, csvBenchmarksPath, evaluationsPath, submittoleaderboardPath } from '../../constants/RouteConstants';

export default function HeaderBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navItems = [
    { label: 'Leaderboard', path: '/' },
    { label: 'Evaluations', path: evaluationsPath },
    { label: 'Submit', path: submittoleaderboardPath },
    { label: 'Add Dataset', path: addDatasetPath },
    { label: 'Benchmarks', path: csvBenchmarksPath },
  ];

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/' || location.pathname === '';
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  return (
    <div className="sticky top-0 z-50 bg-[#0d1117]/95 backdrop-blur-md border-b border-white/[0.06]">
      <div className="max-w-7xl mx-auto px-4">
        <div className="h-14 flex items-center justify-between">
          {/* Logo */}
          <button
            type="button"
            onClick={() => navigate('/')}
            className="flex items-center gap-2.5 shrink-0 group"
            aria-label="Go to leaderboard home"
          >
            <img src="/logo.png" alt="Anote" className="h-7 w-7" />
            <span className="font-bold text-sm tracking-tight">
              <span className="text-white">Anote</span>
              <span className="text-[#28b2fb] ml-1">Leaderboard</span>
            </span>
          </button>

          {/* Desktop nav */}
          <nav className="hidden sm:flex items-center gap-1">
            {navItems.map((item) => (
              <button
                key={item.path}
                type="button"
                onClick={() => navigate(item.path)}
                className={[
                  "px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-150",
                  isActive(item.path)
                    ? "bg-[#defe47] text-black"
                    : "text-gray-400 hover:text-white hover:bg-white/[0.07]"
                ].join(' ')}
              >
                {item.label}
              </button>
            ))}
            <a
              href="https://anote.ai"
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 px-3 py-1.5 rounded-md text-sm font-medium text-[#28b2fb] border border-[#28b2fb]/25 hover:bg-[#28b2fb]/10 transition-all duration-150"
            >
              Anote.ai ↗
            </a>
          </nav>

          {/* Mobile hamburger */}
          <button
            type="button"
            className="sm:hidden p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-white/[0.07] transition-colors"
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
          <div className="sm:hidden pb-3 flex flex-col gap-1 border-t border-white/[0.06] pt-2">
            {navItems.map((item) => (
              <button
                key={item.path}
                type="button"
                onClick={() => { navigate(item.path); setMobileOpen(false); }}
                className={[
                  "px-3 py-2 rounded-md text-sm font-medium text-left transition-all",
                  isActive(item.path)
                    ? "bg-[#defe47] text-black"
                    : "text-gray-400 hover:text-white hover:bg-white/[0.07]"
                ].join(' ')}
              >
                {item.label}
              </button>
            ))}
            <a
              href="https://anote.ai"
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-2 rounded-md text-sm font-medium text-[#28b2fb] hover:bg-[#28b2fb]/10 transition-all"
            >
              Anote.ai ↗
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
