import { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { setLeaderboardJwt } from "../../utils/leaderboardAuth";
import { leaderboardPath } from "../../constants/RouteConstants";

export default function OAuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const raw = typeof window !== "undefined" ? window.location.hash.replace(/^#/, "") : "";
    const params = new URLSearchParams(raw);
    const tok = params.get("access_token");
    const from =
      (location.state && location.state.from) || sessionStorage.getItem("lb_oauth_return") || leaderboardPath;
    sessionStorage.removeItem("lb_oauth_return");
    if (tok) {
      setLeaderboardJwt(tok);
      if (typeof window !== "undefined") {
        window.history.replaceState(null, "", window.location.pathname + window.location.search);
      }
      navigate(from, { replace: true });
    } else {
      navigate("/login", { replace: true });
    }
  }, [navigate, location.state]);

  return (
    <div className="min-h-screen bg-[#111827] text-gray-100 flex items-center justify-center px-4">
      <p className="text-sm text-gray-400">Completing sign-in…</p>
    </div>
  );
}
