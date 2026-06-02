import React from "react";
import ReactDOM from "react-dom/client";

import "@/index.css";
import { DesignSystemPage } from "./page";

const rootElement = document.getElementById("react-design-system-root");

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <DesignSystemPage />
    </React.StrictMode>,
  );
}
