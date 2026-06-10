import React from "react";
import ReactDOM from "react-dom/client";

import "@/index.css";

import { DocumentsPage } from "./page";

const rootElement = document.getElementById("react-documents-root");

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <DocumentsPage apiUrl={rootElement.getAttribute("data-api-url") || "/api/documents/workspace"} />
    </React.StrictMode>,
  );
}
