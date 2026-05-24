// Postinstall: patch @ai-hero/sandcastle to fix stdout buffer overflow.
// The docker sandbox uses Array.join("\n") to concatenate stdout chunks,
// which hits V8's ~256MB string limit on large agent output.
// Switched to Buffer.concat() which has no practical size limit.
const fs = require("fs");
const path = require("path");

const target = path.join(
  __dirname,
  "..",
  "node_modules",
  "@ai-hero/sandcastle",
  "dist",
  "sandboxes",
  "docker.js",
);

let src = fs.readFileSync(target, "utf8");

// Replace the onLine path (line-based callback)
src = src.replace(
  "stdoutChunks.join(\"\\n\")",
  'Buffer.concat(stdoutChunks.map(c => Buffer.from(c + "\\n", "utf-8"))).toString("utf-8")',
);
src = src.replace(
  'stderrChunks.join("")',
  'Buffer.concat(stderrChunks.map(c => Buffer.from(c))).toString("utf-8")',
);

fs.writeFileSync(target, src);
console.log("[postinstall] Patched sandcastle stdout buffer overflow");
