import { createRoot } from "react-dom/client";
import App from "./App";
import { Provider } from "react-redux";
import { store, persistor } from "./stores/store";
import { PersistGate } from "redux-persist/integration/react";
import "./index.css";

const root = createRoot(document.getElementById("root"));
root.render(
  <Provider store={store}>
    <PersistGate loading={null} persistor={persistor}>
      <App />
    </PersistGate>
  </Provider>
);
