import "./landing_page_styles/LandingPage.css";
import "./landing_page_styles/LandingPageFiletypes.css";
import "./landing_page_styles/LandingPageValue.css";
import "./landing_page_styles/LandingPageApplications.css";
import "./landing_page_styles/LandingPageSampleProjects.css";
import "./landing_page_styles/LandingPageEllipse.css";
import "./landing_page_styles/LandingPageLabel.css";
import "./landing_page_styles/LandingPageFooter.css";
import { Routes, Route, Navigate } from "react-router-dom";
import Footer from "./landing_page_components/Footer";
import { Helmet } from "react-helmet";
import { useState, useEffect } from "react";
import { useDispatch } from "react-redux";
import { useLocation } from "react-router-dom";
import { robotHeader } from "../util/RobotHeader";
import Leaderboard from "./landing_page_components/Leaderboard";
import SubmitToLeaderboard  from "./landing_page_components/SubmitToLeaderboard";
import AdminLeaderboardManager from "./landing_page_components/AdminLeaderboardManager";
import AdminSubmissionsModeration from "./landing_page_components/AdminSubmissionsModeration";
import RequestDataset from "./landing_page_components/RequestDataset";
import AdminDatasetRequests from "./landing_page_components/AdminDatasetRequests";
import AddDataset from "./landing_page_components/AddDataset";
import DatasetDetails from "./landing_page_components/DatasetDetails";
import { submittoleaderboardPath, mySubmissionsPath, adminLeaderboardPath, adminSubmissionsPath, adminDatasetRequestsPath, requestDatasetPath, evaluationsPath, csvBenchmarksPath, addDatasetPath, loginPath, oauthCallbackPath, createLeaderboardPath } from "../constants/RouteConstants";
import MySubmissions from "./landing_page_components/MySubmissions";
import HeaderBar from "./landing_page_components/HeaderBar";
import CsvBenchmarksDemo from "./landing_page_components/CsvBenchmarksDemo";
import AuthGuard from "./landing_page_components/AuthGuard";
import LoginPage from "./landing_page_components/LoginPage";
import OAuthCallback from "./landing_page_components/OAuthCallback";
import CreateLeaderboardFromHF from "./landing_page_components/CreateLeaderboardFromHF";

function LandingPage() {
  const location = useLocation();
  let dispatch = useDispatch();

  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const accessToken = localStorage.getItem("accessToken");
    const sessionToken = localStorage.getItem("sessionToken");
    const apiKey = localStorage.getItem("leaderboard_api_key");
    const jwt = sessionStorage.getItem("lb_jwt");
    setIsLoggedIn(!!(accessToken || sessionToken || (apiKey && apiKey.trim()) || jwt));
  }, [location.pathname]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      var path = "lp" + window.location.pathname + window.location.search;
      if (typeof window.gtag === "function") {
        window.gtag("event", "page_view", {
          page_path: path,
        });
      }
      if (isLoggedIn) {
        // dispatch(createVisit(path));
      }
    }
  }, [location, isLoggedIn]);

  let robotMetaTag = robotHeader();

  return (
    <div className="bg-[#111827] min-h-screen">
      <Helmet>
        <title>Anote - Model Leaderboard</title>
        {robotMetaTag}
      </Helmet>

      <HeaderBar />
      {/* <Banner open={open} /> */}
      <div className="pt-14">
        <Routes>
          <Route index element={<Leaderboard />} />,
          <Route path={loginPath} element={<LoginPage />} />,
          <Route path={oauthCallbackPath} element={<OAuthCallback />} />,
          <Route path={submittoleaderboardPath} index element={<AuthGuard><SubmitToLeaderboard /></AuthGuard>} />,
          <Route path={mySubmissionsPath} index element={<AuthGuard><MySubmissions /></AuthGuard>} />,
          <Route path={csvBenchmarksPath} index element={<Navigate replace to="/" />} />,
          <Route path={addDatasetPath} index element={<AuthGuard><AddDataset /></AuthGuard>} />,
          <Route path={createLeaderboardPath} index element={<AuthGuard><CreateLeaderboardFromHF /></AuthGuard>} />,
          <Route path="/dataset/:name" element={<DatasetDetails />} />,
          <Route path={requestDatasetPath} index element={<RequestDataset />} />,
          <Route path={adminLeaderboardPath} index element={<AuthGuard><AdminLeaderboardManager /></AuthGuard>} />,
          <Route path={adminSubmissionsPath} index element={<AuthGuard><AdminSubmissionsModeration /></AuthGuard>} />,
          <Route path={adminDatasetRequestsPath} index element={<AuthGuard><AdminDatasetRequests /></AuthGuard>} />,
          <Route path="*" element={<Navigate replace to="/" />} />
        </Routes>
      </div>
      <Footer />
    </div>
  );
}

export default LandingPage;
