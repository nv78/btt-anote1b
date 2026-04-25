import React from "react";
import { useNavigate } from "react-router-dom";
import {
  addDatasetPath,
  csvBenchmarksPath,
  evaluationsPath,
  submittoleaderboardPath,
} from "../../constants/RouteConstants";

function Footer() {
  const navigate = useNavigate();
  const year = new Date().getFullYear();

  const leaderboardLinks = [
    { label: "View Rankings", path: "/" },
    { label: "Evaluations", path: evaluationsPath },
    { label: "Submit Model", path: submittoleaderboardPath },
    { label: "Add Dataset", path: addDatasetPath },
    { label: "Run Benchmarks", path: csvBenchmarksPath },
  ];

  return (
    <footer className="bg-[#0b1120] border-t border-white/[0.06]">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10">

          {/* Brand */}
          <div>
            <div className="flex items-center gap-2.5 mb-3">
              <img src="/logo.png" alt="Anote" className="h-8 w-8" loading="lazy" />
              <span className="text-lg font-bold text-white">Anote</span>
            </div>
            <p className="text-sm text-gray-400 max-w-xs leading-relaxed mb-4">
              Transparent, community-driven benchmarking for AI models. Compare, submit, and track performance across diverse evaluation datasets.
            </p>
            <a
              href="mailto:nvidra@anote.ai"
              className="text-sm text-[#28b2fb] hover:text-[#defe47] transition-colors"
            >
              nvidra@anote.ai
            </a>
          </div>

          {/* Leaderboard links */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-[#defe47] mb-4">
              Leaderboard
            </h3>
            <ul className="space-y-2.5">
              {leaderboardLinks.map(({ label, path }) => (
                <li key={path}>
                  <button
                    type="button"
                    onClick={() => navigate(path)}
                    className="text-sm text-gray-400 hover:text-white transition-colors"
                  >
                    {label}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* Connect */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-[#defe47] mb-4">
              Connect
            </h3>
            <ul className="space-y-2.5">
              <li>
                <a
                  href="https://anote.ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-gray-400 hover:text-white transition-colors"
                >
                  Anote.ai →
                </a>
              </li>
              <li>
                <a
                  href="https://anote-ai.medium.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-gray-400 hover:text-white transition-colors"
                >
                  Blog
                </a>
              </li>
              <li>
                <a
                  href="https://www.linkedin.com/company/anote-ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-gray-400 hover:text-white transition-colors"
                >
                  LinkedIn
                </a>
              </li>
              <li>
                <a
                  href="https://docs.anote.ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-gray-400 hover:text-white transition-colors"
                >
                  Documentation
                </a>
              </li>
            </ul>
          </div>

        </div>

        {/* Bottom bar */}
        <div className="mt-10 pt-6 border-t border-gray-800/50 flex flex-col sm:flex-row justify-between items-center gap-3">
          <p className="text-xs text-gray-500">© {year} Anote. All rights reserved.</p>
          <div className="flex items-center gap-4">
            <a
              href="https://anote.ai/privacypolicy"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              Privacy Policy
            </a>
            {/* Social icons */}
            <div className="flex items-center gap-3 ml-2">
              <a
                href="https://anote-ai.medium.com/"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Medium"
                className="text-gray-500 hover:text-white transition-colors"
              >
                <img className="w-4 h-4 opacity-60 hover:opacity-100 transition-opacity" src="/landing_page_assets/social/medium.svg" alt="Medium" loading="lazy" />
              </a>
              <a
                href="https://www.linkedin.com/company/anote-ai"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="LinkedIn"
                className="text-gray-500 hover:text-[#28b2fb] transition-colors"
              >
                <svg fill="currentColor" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="0" className="w-4 h-4" viewBox="0 0 24 24">
                  <path stroke="none" d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-2-2 2 2 0 00-2 2v7h-4v-7a6 6 0 016-6zM2 9h4v12H2z" />
                  <circle cx="4" cy="4" r="2" stroke="none" />
                </svg>
              </a>
            </div>
          </div>
        </div>

      </div>
    </footer>
  );
}

export default Footer;
