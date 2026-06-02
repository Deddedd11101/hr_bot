import React from "react";
import { createRoot } from "react-dom/client";

import { ShellSidebarPage } from "./page";

const rootElement = document.getElementById("react-shell-sidebar-root");

if (rootElement) {
  const activeTab = rootElement.dataset.activeTab ?? "";
  const roleLabel = rootElement.dataset.roleLabel ?? "Оператор";

  createRoot(rootElement).render(
    <React.StrictMode>
      <ShellSidebarPage activeTab={activeTab} roleLabel={roleLabel} />
    </React.StrictMode>,
  );
}
