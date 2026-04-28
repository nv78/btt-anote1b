const JWT_KEY = "lb_jwt";

export function getLeaderboardJwt() {
  if (typeof sessionStorage === "undefined") return "";
  return sessionStorage.getItem(JWT_KEY) || "";
}

export function setLeaderboardJwt(token) {
  if (typeof sessionStorage === "undefined") return;
  if (token) sessionStorage.setItem(JWT_KEY, token);
  else sessionStorage.removeItem(JWT_KEY);
}

export function clearLeaderboardJwt() {
  setLeaderboardJwt("");
}

/** True if the guarded SPA routes can proceed (JWT session or integrator API key). */
export function canAccessContributorRoutes() {
  if (typeof localStorage === "undefined") return !!getLeaderboardJwt();
  const apiKey = localStorage.getItem("leaderboard_api_key") || "";
  return !!(getLeaderboardJwt() || apiKey.trim());
}
