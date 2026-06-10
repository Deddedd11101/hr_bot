import React from "react";
import ReactDOM from "react-dom/client";

import "@/index.css";

import { LoginPage } from "./page";

const rootElement = document.getElementById("react-login-root");

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <LoginPage errorMessage={rootElement.getAttribute("data-error-message") || ""} />
    </React.StrictMode>
  );
}
