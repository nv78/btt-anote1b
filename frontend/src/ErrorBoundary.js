import React from "react";

let ReactGA4;
try {
  ReactGA4 = require("react-ga4").default;
} catch (e) {
  ReactGA4 = null;
}

class ErrorBoundary extends React.Component {
  state = { error: null, hasError: false };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error("ErrorBoundary caught an error:", error, info);

    if (ReactGA4) {
      try {
        ReactGA4.event({
          category: "Error",
          action: "Uncaught React Error",
          label: error && error.message ? error.message : String(error),
        });
      } catch (gaError) {
        console.error("GA4 event failed:", gaError);
      }
    }
  }

  handleReset = () => {
    this.setState({ error: null, hasError: false });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100vh",
            fontFamily: "sans-serif",
            padding: "2rem",
            textAlign: "center",
          }}
        >
          <h1 style={{ fontSize: "1.5rem", marginBottom: "1rem" }}>
            Something went wrong.
          </h1>
          <p style={{ color: "#555", marginBottom: "1.5rem" }}>
            An unexpected error occurred. Please try again.
          </p>
          <button
            onClick={this.handleReset}
            style={{
              padding: "0.6rem 1.4rem",
              fontSize: "1rem",
              cursor: "pointer",
              borderRadius: "4px",
              border: "1px solid #ccc",
              background: "#fff",
            }}
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
