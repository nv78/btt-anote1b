import { Navigate, useLocation } from "react-router-dom";
import { canAccessContributorRoutes } from "../../utils/leaderboardAuth";
import { loginPath } from "../../constants/RouteConstants";

export default function AuthGuard({ children }) {
  const location = useLocation();
  if (!canAccessContributorRoutes()) {
    return <Navigate to={loginPath} replace state={{ from: location.pathname }} />;
  }
  return children;
}
