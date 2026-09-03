import React from "react";
import ReactDOM from "react-dom/client";

import "@/index.css";

import { MessagesPage } from "./page";

const rootElement = document.getElementById("react-messages-root");

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <MessagesPage apiUrl={rootElement.getAttribute("data-api-url") || "/api/bulk-actions/workspace"} />
    </React.StrictMode>
  );
}
