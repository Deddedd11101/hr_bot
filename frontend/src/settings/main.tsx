import React from "react";
import ReactDOM from "react-dom/client";

import "@/index.css";

import { SettingsPage } from "./page";

const rootElement = document.getElementById("react-settings-root");

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <SettingsPage
        apiUrl={rootElement.getAttribute("data-api-url") || "/api/settings/workspace"}
        classicUrl={rootElement.getAttribute("data-classic-url") || "/settings"}
      />
    </React.StrictMode>
  );
}
