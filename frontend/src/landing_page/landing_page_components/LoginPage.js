import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { leaderboardPath } from "../../constants/RouteConstants";

const API_BASE =
  process.env.REACT_APP_API_BASE || process.env.REACT_APP_API_ENDPOINT || "http://localhost:5001";

export default function LoginPage() {
  const location = useLocation();
  const from = (location.state && location.state.from) || leaderboardPath;

  useEffect(() => {
    const st = location.state && location.state.from;
    if (st && typeof st === "string") {
      sessionStorage.setItem("lb_oauth_return", st);
    }
  }, [location.state]);
  const googleStart = `${API_BASE}/public/auth/google/start`;

  return (
    <div className="min-h-screen bg-[#111827] text-gray-100 py-16 px-4">
      <div className="max-w-md mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-white">Sign in</h1>
        <p className="text-sm text-gray-400">
          Contributors can sign in with Google (when the API has OAuth configured), or use an API key on the Submit page.
        </p>
        <a
          href={googleStart}
          className="inline-flex items-center justify-center w-full px-4 py-3 rounded-lg bg-white text-gray-900 font-semibold hover:bg-gray-100"
        >
          Continue with Google
        </a>
        <p className="text-xs text-gray-500">
          After login you will return to: <code className="text-gray-400">{from}</code>
        </p>
        <Link to={leaderboardPath} className="block text-center text-sm text-[#defe47] hover:underline">
          Back to leaderboard
        </Link>
      </div>
    </div>
  );
}
