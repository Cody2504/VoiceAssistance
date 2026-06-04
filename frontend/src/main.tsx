import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router";
import { Toaster } from "sonner";

import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
// ElevenLabs-style display serif (Waldenburg substitute) + technical mono
import "@fontsource/cormorant-garamond/300.css";
import "@fontsource/cormorant-garamond/400.css";
import "@fontsource/cormorant-garamond/500.css";
import "@fontsource/geist-mono/400.css";

import App from "@/App";
import { AuthProvider } from "@/contexts/AuthContext";
import "@/utils/setupAxios";
import "@/i18n";
import "@/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
