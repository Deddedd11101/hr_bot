import React from "react";
import { createRoot } from "react-dom/client";

import { DashboardPage } from "./page";

const rootElement = document.getElementById("react-dashboard-root");

if (rootElement) {
  createRoot(rootElement).render(
    <React.StrictMode>
      <DashboardPage apiUrl={rootElement.getAttribute("data-api-url") || "/api/dashboard/workspace"} />
    </React.StrictMode>
  );
}
