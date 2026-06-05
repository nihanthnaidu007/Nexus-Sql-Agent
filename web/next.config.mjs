/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produce a self-contained server bundle (.next/standalone) so the Docker
  // runtime image stays lean — it copies the standalone output and runs
  // `node server.js` without the full node_modules tree.
  output: "standalone",
};

export default nextConfig;
