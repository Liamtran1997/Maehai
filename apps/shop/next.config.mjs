import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "../..");

/** @type {import('next').NextConfig} */
export default {
  transpilePackages: ["@maehai/ui", "@maehai/api-client"],
  output: "standalone",          // small self-contained server for the Docker image
  outputFileTracingRoot: root,   // monorepo: trace workspace packages from the repo root
  poweredByHeader: false,
};
