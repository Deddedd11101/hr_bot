import React from "react";
import ReactDOM from "react-dom/client";

import "@/index.css";

import { BulkActionsPage } from "./page";

const rootElement = document.getElementById("react-bulk-actions-root");

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <BulkActionsPage
        apiUrl={rootElement.getAttribute("data-api-url") || "/api/bulk-actions/workspace"}
        classicUrl={rootElement.getAttribute("data-classic-url") || "/bulk-actions"}
      />
    </React.StrictMode>
  );
}
