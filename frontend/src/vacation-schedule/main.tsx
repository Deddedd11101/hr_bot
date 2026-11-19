import React from "react";
import { createRoot } from "react-dom/client";
import "@/index.css";
import { VacationSchedule } from "./page";

const root = document.getElementById("react-vacation-schedule-root");
if (root) createRoot(root).render(<React.StrictMode><VacationSchedule /></React.StrictMode>);
