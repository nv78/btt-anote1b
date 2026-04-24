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
import Evaluations  from "./landing_page_components/Evaluations"
import AdminLeaderboardManager from "./landing_page_components/AdminLeaderboardManager";
import AddDataset from "./landing_page_components/AddDataset";
import DatasetDetails from "./landing_page_components/DatasetDetails";
import { submittoleaderboardPath, adminLeaderboardPath, evaluationsPath, csvBenchmarksPath, addDatasetPath } from "../constants/RouteConstants";
import HeaderBar from "./landing_page_components/HeaderBar";
import CsvBenchmarksDemo from "./landing_page_components/CsvBenchmarksDemo";

function LandingPage() {
  const location = useLocation();
  let dispatch = useDispatch();

  const [isLoggedIn, setIsLoggedIn] = useState(true);
  const accessToken = localStorage.getItem("accessToken");
  const sessionToken = localStorage.getItem("sessionToken");
  if (accessToken || sessionToken) {
    if (!isLoggedIn) {
      setIsLoggedIn(true);
    }
  } else {
    if (isLoggedIn) {
      setIsLoggedIn(false);
    }
  }

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
          <Route path={submittoleaderboardPath} index element={<SubmitToLeaderboard />} />,
          <Route path={evaluationsPath} index element={<Evaluations />} />,
          <Route path={csvBenchmarksPath} index element={<CsvBenchmarksDemo />} />,
          <Route path={addDatasetPath} index element={<AddDataset />} />,
          <Route path="/dataset/:name" element={<DatasetDetails />} />,
          <Route path={adminLeaderboardPath} index element={<AdminLeaderboardManager />} />,
          <Route path="*" element={<Navigate replace to="/" />} />
        </Routes>
      </div>
      <Footer />
    </div>
  );
}

export default LandingPage;
