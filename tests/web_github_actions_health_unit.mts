/**
 * GitHub Actions health helper unit harness.
 * Invoked via npx tsx from web/ after staging.
 */
import assert from "node:assert/strict";

import {
  githubActionsHealthEnabled,
  queryGithubActionsHealth,
  resolveHealthGithubRepo,
} from "./src/lib/api/github-actions-health.ts";

function testRepoResolve() {
  assert.equal(resolveHealthGithubRepo(undefined), "ArdenoStudio/Koel");
  assert.equal(resolveHealthGithubRepo("ArdenoStudio/Koel"), "ArdenoStudio/Koel");
  // Legacy fork / old Vercel env defaults must not point Health at the fork.
  assert.equal(resolveHealthGithubRepo("Cookie-Cat21/Koel"), "ArdenoStudio/Koel");
  assert.equal(resolveHealthGithubRepo("cookie-cat21/koel"), "ArdenoStudio/Koel");
  assert.equal(resolveHealthGithubRepo("Cookie-Cat21/Other"), "ArdenoStudio/Koel");
  assert.equal(resolveHealthGithubRepo("../evil"), "ArdenoStudio/Koel");
  assert.equal(resolveHealthGithubRepo("https://evil"), "ArdenoStudio/Koel");
}

async function testFetchPickLatest() {
  process.env.HEALTH_GITHUB_ACTIONS = "1";
  assert.equal(githubActionsHealthEnabled(), true);
  const fetchImpl = (async () =>
    new Response(
      JSON.stringify({
        workflow_runs: [
          {
            name: "CI",
            status: "completed",
            conclusion: "success",
            head_branch: "main",
            event: "push",
            run_number: 10,
            html_url: "https://github.com/ArdenoStudio/Koel/actions/runs/10",
            updated_at: "2026-07-19T12:00:00Z",
          },
          {
            name: "CI",
            status: "completed",
            conclusion: "failure",
            head_branch: "feat",
            event: "pull_request",
            run_number: 9,
            html_url: "https://github.com/ArdenoStudio/Koel/actions/runs/9",
            updated_at: "2026-07-19T11:00:00Z",
          },
          {
            name: "ML self-learn",
            status: "completed",
            conclusion: "success",
            head_branch: "main",
            event: "schedule",
            run_number: 3,
            html_url: "https://github.com/ArdenoStudio/Koel/actions/runs/3",
            updated_at: "2026-07-19T10:00:00Z",
          },
        ],
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    )) as typeof fetch;

  const block = await queryGithubActionsHealth(fetchImpl);
  assert.ok(block);
  assert.equal(block!.repo, "ArdenoStudio/Koel");
  assert.equal(block!.runs.length, 2);
  assert.equal(block!.runs[0]!.workflow, "CI");
  assert.equal(block!.runs[0]!.conclusion, "success");
  assert.equal(block!.runs[0]!.run_number, 10);
  assert.equal(block!.runs[1]!.workflow, "ML self-learn");

  process.env.HEALTH_GITHUB_ACTIONS = "0";
  assert.equal(githubActionsHealthEnabled(), false);
  assert.equal(await queryGithubActionsHealth(fetchImpl), null);
  delete process.env.HEALTH_GITHUB_ACTIONS;
}

await testRepoResolve();
await testFetchPickLatest();
console.log("WEB_GITHUB_ACTIONS_HEALTH_UNIT_OK");
