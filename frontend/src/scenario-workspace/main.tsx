import ReactDOM from "react-dom/client";

import "@/index.css";

import { ScenarioWorkspacePage } from "./page";

const rootElement = document.getElementById("react-scenario-workspace-v2-root");

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(<ScenarioWorkspacePage />);
}
