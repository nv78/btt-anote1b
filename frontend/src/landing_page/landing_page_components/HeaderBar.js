import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { addDatasetPath, csvBenchmarksPath, evaluationsPath, submittoleaderboardPath } from '../../constants/RouteConstants';

export default function HeaderBar() {
  const location = useLocation();
  const navigate = useNavigate();
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
    <div className="sticky top-0 z-50 border-b border-[#defe47]/20 bg-[#111827]/95 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 min-h-14 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 py-3">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-left"
          aria-label="Go to leaderboard home"
        >
          <img src="/logo.png" alt="Anote" className="h-7 w-7" />
          <span className="font-semibold text-white">Anote Leaderboard</span>
        </button>
        <nav className="flex flex-wrap items-center gap-2">
          {navItems.map((item) => (
            <button
              key={item.path}
              type="button"
              onClick={() => navigate(item.path)}
              className={[
                "px-3 py-1.5 rounded-md text-sm border transition-colors",
                isActive(item.path)
                  ? "border-[#defe47] bg-[#defe47] text-black"
                  : "border-gray-800 text-gray-300 hover:border-[#defe47]/60 hover:text-[#defe47]"
              ].join(' ')}
            >
              {item.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => window.open('https://anote.ai', '_blank', 'noopener,noreferrer')}
            className="px-3 py-1.5 rounded-md text-sm border border-gray-800 text-gray-400 hover:border-gray-600 hover:text-white transition-colors"
          >
            Anote.ai
          </button>
        </nav>
      </div>
    </div>
  );
}
