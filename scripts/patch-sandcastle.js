// Postinstall: patch @ai-hero/sandcastle to cap stdout/stderr size.
// V8 has a hard ~512MB string length limit. Large agent output (full test
// suites, verbose ruff, agent reasoning) routinely exceeds this.
//
// Strategy: truncate to the last 5000 lines / 500KB so the result fits
// in memory while preserving the most relevant output (failures at the end).
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

const MAX_LINES = 5000;
const MAX_BYTES = 500_000;

let src = fs.readFileSync(target, "utf8");

// --- onLine path: keep last MAX_LINES lines ---
src = src.replace(
  "stdoutChunks.join(\"\\n\")",
  `(stdoutChunks.length > ${MAX_LINES} ? stdoutChunks.slice(-${MAX_LINES}) : stdoutChunks).join("\\n")`,
);
// stderr in onLine path: same treatment
src = src.replace(
  'stderrChunks.join("")',
  `(stderrChunks.length > ${MAX_LINES} ? stderrChunks.slice(-${MAX_LINES}) : stderrChunks).join("")`,
);

// --- non-onLine path: keep last MAX_BYTES ---
src = src.replace(
  "Buffer.concat(stdoutChunks).toString(\"utf-8\")",
  `((b) => b.length > ${MAX_BYTES} ? b.slice(-${MAX_BYTES}) : b)(Buffer.concat(stdoutChunks)).toString("utf-8")`,
);
src = src.replace(
  "Buffer.concat(stderrChunks).toString(\"utf-8\")",
  `((b) => b.length > ${MAX_BYTES} ? b.slice(-${MAX_BYTES}) : b)(Buffer.concat(stderrChunks)).toString("utf-8")`,
);

fs.writeFileSync(target, src);
console.log("[postinstall] Patched sandcastle stdout truncation guard");
