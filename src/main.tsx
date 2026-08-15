import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";

import "./styles/index.css";

import router from "@/router/routes";
import queryClient from "@/lib/query";
import { ThemeProvider } from "@/theme/ThemeProvider";
import CreateFormDateGuard from "@/components/form/CreateFormDateGuard";

import useAuthStore from "@/store/auth";

/*
 * Restore authentication from localStorage before the app renders.
 */
useAuthStore.getState().initialize();

ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <CreateFormDateGuard />
        <RouterProvider router={router} />

        <Toaster
          position="top-right"
          richColors
          closeButton
          duration={3000}
        />
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
);