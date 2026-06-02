import React from "react";
import ReactDOM from "react-dom/client";

import "@/index.css";
import "./employee-detail.css";
import { EmployeeDetailPage } from "./page";

const rootElement = document.getElementById("react-employee-edit-root");

if (rootElement) {
    ReactDOM.createRoot(rootElement).render(
        <React.StrictMode>
            <EmployeeDetailPage
                apiUrl={rootElement.dataset.apiUrl || ""}
                saveUrl={rootElement.dataset.saveUrl || ""}
                listUrl={rootElement.dataset.listUrl || ""}
                flashMessage={rootElement.dataset.flashMessage || ""}
                flashType={rootElement.dataset.flashType || ""}
            />
        </React.StrictMode>
    );
}
