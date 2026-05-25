/**
 * One-shot: run the reviewer on an existing un-reviewed branch.
 *
 * Usage:
 *   npx tsx .sandcastle/review-only.mts sandcastle/issue-<N>-<slug>
 */

import * as sandcastle from "@ai-hero/sandcastle";
import { docker } from "@ai-hero/sandcastle/sandboxes/docker";

const BRANCH = process.argv[2];
if (!BRANCH) {
  console.error("Usage: npx tsx .sandcastle/review-only.mts <branch>");
  process.exit(1);
}

const hooks = {
  sandbox: {
    onSandboxReady: [{ command: "pip install --break-system-packages -r requirements.txt" }],
  },
};

console.log(`Running reviewer on branch: ${BRANCH}`);

await using sandbox = await sandcastle.createSandbox({
  branch: BRANCH,
  sandbox: docker(),
  hooks,
});

const result = await sandbox.run({
  name: "reviewer",
  maxIterations: 1,
  agent: sandcastle.pi("deepseek-v4-pro"),
  promptFile: "./.sandcastle/review-prompt.md",
  promptArgs: { BRANCH },
});

console.log(`\nReview complete. Commits: ${result.commits.length}`);
for (const c of result.commits) {
  console.log(`  ${c.sha}`);
}
