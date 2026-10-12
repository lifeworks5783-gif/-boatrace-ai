// Lightweight scheduler only. No scoring, signal thresholds, or race data are changed.
// Set secret GITHUB_TOKEN with workflow/actions:write permission before deployment.
const API = "https://api.github.com";
function jstHour(now) { return Number(new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Tokyo",hour:"2-digit",hourCycle:"h23"}).format(now)); }
async function github(url, token, options={}) {
  const response = await fetch(API+url,{...options,headers:{"Authorization":`Bearer ${token}`,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"boatrace-cloudflare-dispatch",...(options.headers||{})}});
  if (!response.ok) throw new Error(`GitHub API ${response.status}: ${(await response.text()).slice(0,200)}`);
  return response.status === 204 ? null : response.json();
}
export default {
  async scheduled(event,env,ctx){ ctx.waitUntil(run(env)); },
  async fetch(request){ return new Response("Boatrace scheduled dispatcher configured",{status:200}); }
};
async function run(env){
  if (!env.GITHUB_TOKEN) throw new Error("GITHUB_TOKEN secret is not configured");
  if (jstHour(new Date()) < 6) return;
  const repo = env.GITHUB_REPOSITORY;
  const workflow = env.WORKFLOW_FILE || "fast_live_collection_v3.yml";
  // Do not queue overlapping collection runs. GitHub concurrency remains the
  // authoritative second guard for races created concurrently.
  const runs = await github(`/repos/${repo}/actions/workflows/${workflow}/runs?per_page=30`,env.GITHUB_TOKEN);
  if ((runs.workflow_runs||[]).some(x=>x.status!=="completed")) return;
  await github(`/repos/${repo}/actions/workflows/${workflow}/dispatches`,env.GITHUB_TOKEN,{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({ref:"main",inputs:{quick_mode:"true"}})
  });
}
