import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import net from "net";

const API_PROXY_TARGET = "http://localhost:8000";

// #region agent log
function debugSessionLog(payload: Record<string, unknown>) {
  fetch("http://127.0.0.1:7273/ingest/4ca968ae-e1b2-4f1b-a3cb-87c1f7eee48f", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Debug-Session-Id": "af7d33",
    },
    body: JSON.stringify({
      sessionId: "af7d33",
      timestamp: Date.now(),
      ...payload,
    }),
  }).catch(() => {});
}

function debugProxyPlugin(): Plugin {
  return {
    name: "debug-proxy-session",
    configureServer(server) {
      server.httpServer?.once("listening", () => {
        debugSessionLog({
          location: "vite.config.ts:listening",
          message: "dev server up; proxy target",
          hypothesisId: "H2",
          data: { proxyTarget: API_PROXY_TARGET, apiPath: "/api" },
        });
        const socket = net.createConnection({ port: 8000, host: "127.0.0.1" });
        socket.on("connect", () => {
          debugSessionLog({
            location: "vite.config.ts:probe-connect",
            message: "TCP connect to backend port succeeded",
            hypothesisId: "H1",
            data: { host: "127.0.0.1", port: 8000, reachable: true },
          });
          socket.end();
        });
        socket.on("error", (err: NodeJS.ErrnoException) => {
          debugSessionLog({
            location: "vite.config.ts:probe-error",
            message: "TCP connect to backend port failed",
            hypothesisId: "H1",
            data: {
              host: "127.0.0.1",
              port: 8000,
              reachable: false,
              code: err.code,
              errMessage: err.message,
            },
          });
          server.config.logger.warn(
            `\n[ektasearch] No API on port 8000 (${err.code}). Vite proxies /api to ${API_PROXY_TARGET}. From the backend folder run: uvicorn app.main:app --reload --host 127.0.0.1 --port 8000\n`,
          );
        });
      });
    },
  };
}
// #endregion

export default defineConfig({
  plugins: [react(), debugProxyPlugin()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: API_PROXY_TARGET,
        changeOrigin: true,
        // #region agent log
        configure: (proxy) => {
          proxy.on("error", (err: Error & NodeJS.ErrnoException) => {
            debugSessionLog({
              location: "vite.config.ts:proxy-on-error",
              message: "vite http-proxy error forwarding /api",
              hypothesisId: "H3",
              data: {
                target: API_PROXY_TARGET,
                code: err.code,
                errMessage: err.message,
              },
            });
          });
        },
        // #endregion
      },
    },
  },
});
