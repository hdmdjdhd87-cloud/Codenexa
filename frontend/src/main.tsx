import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "@/app/App";
import { initTelegram } from "@/lib/telegram";
import "@/styles/globals.css";

// Telegram injects WebApp before the app is mounted, but explicitly
// initialize it here so ready/expand are called before authentication starts.
initTelegram();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
