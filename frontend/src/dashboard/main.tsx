import React from "react";
import { createRoot } from "react-dom/client";

import { DashboardPage } from "./page";
import { QueuePage } from "./operations";

const rootElement = document.getElementById("react-dashboard-root");

if (rootElement) {
  createRoot(rootElement).render(
    <React.StrictMode>
      {rootElement.dataset.queuePage === "true" ? <QueuePage /> : <DashboardPage apiUrl={rootElement.getAttribute("data-api-url") || "/api/dashboard/workspace"} />}
    </React.StrictMode>
  );
}
