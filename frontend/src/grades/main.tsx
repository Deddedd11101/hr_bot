import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import { GradesPage } from "./page";
const root = document.getElementById("react-grades-root");
if (root) ReactDOM.createRoot(root).render(<React.StrictMode><GradesPage /></React.StrictMode>);
