import { defineConfig } from "vite";

export default defineConfig(() => {
  const enableLan = process.env.VITE_LAN === "1";
  return {
    server: {
      port: 5173,
      host: enableLan ? true : "localhost",
      ...(enableLan ? { allowedHosts: ["c-macbook.local"] } : {}),
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
