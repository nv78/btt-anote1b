import LandingPage from "./landing_page/LandingPage";
import ErrorBoundary from "./ErrorBoundary";
import ReactGA4 from "react-ga4";
import { BrowserRouter as Router, useLocation } from "react-router-dom";
import { useEffect } from "react";

const GA_ID = process.env.REACT_APP_GA_ID;
if (GA_ID) {
  ReactGA4.initialize(GA_ID);
}

function PageTracker({subdomain}) {
  let location = useLocation();

  useEffect(() => {
    if (GA_ID) {
      ReactGA4.send({
        hitType: 'pageview',
        page: subdomain + "/" + location.pathname,
      });
    }
  }, [location, subdomain]);

  return null; // This component does not render anything
}

function App() {
  return (
    <ErrorBoundary>
      <Router>
        <PageTracker subdomain="landingpage" />
        <LandingPage />
      </Router>
    </ErrorBoundary>
  );
}

export default App;
