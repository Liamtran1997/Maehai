import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// VITE_BASE is "/admin/" in the Docker build, where the admin lives under the same domain as the shop.
export default defineConfig({ base: process.env.VITE_BASE ?? "/", plugins: [react()], server: { port: 5173 } });
