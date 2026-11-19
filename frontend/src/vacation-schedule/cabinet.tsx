import React from "react";
import { createRoot } from "react-dom/client";
import "@/index.css";
import { VacationSchedule } from "./page";

const theme = matchMedia("(prefers-color-scheme: dark)");
const sync = () => document.documentElement.classList.toggle("dark", theme.matches);
sync(); theme.addEventListener("change", sync);
const root = document.getElementById("cabinet-gantt-root");
if (root) createRoot(root).render(<React.StrictMode><VacationSchedule embedded /></React.StrictMode>);
new ResizeObserver(() => window.parent.postMessage({type: "cabinet-gantt-height", height: document.body.scrollHeight}, location.origin)).observe(document.body);
