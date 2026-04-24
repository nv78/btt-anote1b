import React from "react";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Keep this local; production telemetry can hook in here later.
    console.error("App render error", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center px-6 text-center">
          <h1 className="text-2xl font-semibold text-[#EDDC8F]">Something went wrong.</h1>
          <button
            className="mt-4 px-4 py-2 rounded-md border border-gray-700 hover:bg-gray-800"
            onClick={() => this.setState({ error: null })}
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
