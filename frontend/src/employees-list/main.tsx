import ReactDOM from "react-dom/client";

import "@/index.css";

import { EmployeesListPage } from "./page";
import type { ListKind } from "./types";

const rootElement = document.getElementById("react-employees-root");

if (rootElement) {
  const apiBaseUrl = rootElement.getAttribute("data-api-base-url") || "/api/employees";
  const createUrl = rootElement.getAttribute("data-create-url") || "/api/employees";
  const defaultListKind = (rootElement.getAttribute("data-default-list-kind") || "employees") as ListKind;

  ReactDOM.createRoot(rootElement).render(
    <EmployeesListPage
      apiBaseUrl={apiBaseUrl}
      createUrl={createUrl}
      defaultListKind={defaultListKind}
    />,
  );
}
