import React from "react";
import ReactDOM from "react-dom/client";

import "@/index.css";

import { BotMenuPage } from "./page";

const rootElement = document.getElementById("react-bot-menu-root");

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <BotMenuPage
        apiUrl={rootElement.getAttribute("data-api-url") || "/api/settings/workspace"}
      />
    </React.StrictMode>,
  );
}
