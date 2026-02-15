import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "convex/react";
import { api } from "../../convex/_generated/api";
import type { Id } from "../../convex/_generated/dataModel";
import SettingsDialog from "@/components/SettingsDialog";

// --- Log ticker: rapidly flashes through queued lines ---

function useLogTicker() {
  const [line, setLine] = useState("");
  const queue = useRef<string[]>([]);
  const running = useRef(false);

  function flush() {
    if (running.current) return;
    running.current = true;
    (function tick() {
      const next = queue.current.shift();
      if (next === undefined) {
        running.current = false;
        return;
      }
      setLine(next);
      setTimeout(tick, 80);
    })();
  }

  function push(...lines: string[]) {
    queue.current.push(...lines);
    flush();
  }

  return { line, push };
}

// --- Derive dashboard stats from events ---

interface DashboardStats {
  activeResearchers: number;
  activeReviewers: number;
  totalResearchers: number;
  totalReviewers: number;
  prs: { pr: number; agent_id: string; repo?: string }[];
  browserUrls: { url: string; agent: string }[];
  pipelineStatus: string;
  elapsedSeconds: number | null;
  taskCount: number | null;
}

function useStats(events: { type: string; data: Record<string, unknown> }[] | undefined): DashboardStats {
  return useMemo(() => {
    const stats: DashboardStats = {
      activeResearchers: 0,
      activeReviewers: 0,
      totalResearchers: 0,
      totalReviewers: 0,
      prs: [],
      browserUrls: [],
      pipelineStatus: "waiting",
      elapsedSeconds: null,
      taskCount: null,
    };
    if (!events) return stats;

    let researchStarted = 0;
    let researchDone = 0;
    let reviewStarted = 0;
    let reviewDone = 0;

    for (const e of events) {
      const d = e.data as Record<string, unknown>;
      switch (e.type) {
        case "pipeline_started":
          stats.pipelineStatus = "running";
          break;
        case "orchestrator_done":
          stats.taskCount = (d.taskCount as number) ?? null;
          break;
        case "researcher_started":
          researchStarted++;
          break;
        case "researcher_done":
          researchDone++;
          break;
        case "reviewer_started":
          reviewStarted++;
          break;
        case "reviewer_done":
          reviewDone++;
          break;
        case "pr_created":
          stats.prs.push({
            pr: d.pr as number,
            agent_id: d.agent_id as string,
            repo: d.repo as string | undefined,
          });
          break;
        case "browser_url":
          stats.browserUrls.push({
            url: d.url as string,
            agent: d.agent as string,
          });
          break;
        case "pipeline_done":
          stats.pipelineStatus = "completed";
          stats.elapsedSeconds = (d.elapsedSeconds as number) ?? null;
          break;
      }
    }

    stats.totalResearchers = researchStarted;
    stats.totalReviewers = reviewStarted;
    stats.activeResearchers = researchStarted - researchDone;
    stats.activeReviewers = reviewStarted - reviewDone;
    return stats;
  }, [events]);
}

// --- Component ---

export default function SessionView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const sessionId = id as Id<"sessions">;

  const logs = useQuery(api.sessions.getSessionLogs, { sessionId });
  const events = useQuery(api.sessions.getSessionEvents, { sessionId });
  const stats = useStats(events);
  const { line, push } = useLogTicker();

  // Feed new log batches into the ticker as they arrive
  const seenLogs = useRef(0);
  useEffect(() => {
    if (!logs) return;
    if (logs.length > seenLogs.current) {
      const newBatches = logs.slice(seenLogs.current);
      seenLogs.current = logs.length;
      const lines = newBatches.flatMap((b) => b.text.split("\n").filter(Boolean));
      push(...lines);
    }
  }, [logs, push]);

  return (
    <div className="min-h-screen bg-background/50 pb-32">
      <main className="w-full px-6 py-10">
        {/* Stats grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6 max-w-3xl">
          <StatCard label="Researchers" active={stats.activeResearchers} total={stats.totalResearchers} />
          <StatCard label="Reviewers" active={stats.activeReviewers} total={stats.totalReviewers} />
          <div className="border border-border bg-background px-4 py-3">
            <p className="text-xs text-muted-foreground">Tasks</p>
            <p className="text-lg font-bold">{stats.taskCount ?? "--"}</p>
          </div>
          <div className="border border-border bg-background px-4 py-3">
            <p className="text-xs text-muted-foreground">Status</p>
            <p className="text-lg font-bold">{stats.pipelineStatus}</p>
          </div>
        </div>

        {/* PRs */}
        {stats.prs.length > 0 && (
          <div className="mb-6 max-w-3xl">
            <h3 className="text-sm font-medium text-muted-foreground mb-2">Pull Requests</h3>
            <div className="border border-border bg-background divide-y divide-border">
              {stats.prs.map((pr) => (
                <div key={pr.pr} className="px-4 py-2 text-sm flex items-center justify-between">
                  <span className="font-mono">PR #{pr.pr}</span>
                  <span className="text-muted-foreground text-xs">{pr.agent_id}</span>
                  {pr.repo && (
                    <a
                      href={`https://github.com/${pr.repo}/pull/${pr.pr}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:underline text-xs"
                    >
                      view
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Browser URLs */}
        {stats.browserUrls.length > 0 && (
          <div className="mb-6 max-w-3xl">
            <h3 className="text-sm font-medium text-muted-foreground mb-2">Browser Sessions</h3>
            <div className="border border-border bg-background divide-y divide-border">
              {stats.browserUrls.map((b, i) => (
                <div key={i} className="px-4 py-2 text-sm flex items-center justify-between">
                  <span className="text-muted-foreground text-xs">{b.agent}</span>
                  <a
                    href={b.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent hover:underline text-xs font-mono truncate max-w-[300px]"
                  >
                    {b.url}
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Elapsed */}
        {stats.elapsedSeconds !== null && (
          <p className="text-sm text-muted-foreground">
            Completed in {Math.floor(stats.elapsedSeconds / 60)}m {stats.elapsedSeconds % 60}s
          </p>
        )}
      </main>

      {/* Breadcrumb - positioned above bottom bar */}
      <div className="fixed bottom-16 left-0 right-0 px-6 py-3 bg-background/50">
        <div className="flex items-center gap-2 text-sm">
          <span
            className="text-muted-foreground cursor-pointer hover:text-foreground transition-colors"
            onClick={() => navigate("/sessions")}
          >
            Sessions
          </span>
          <span className="text-muted-foreground">/</span>
          <span className="font-mono text-xs">{id}</span>
        </div>
      </div>

      {/* Bottom bar with log ticker */}
      <nav className="fixed bottom-0 left-0 right-0 border-t-3 border-bee-black bg-primary px-6 py-3 flex items-center justify-between">
        <h1
          className="text-lg font-bold tracking-tight text-primary-foreground cursor-pointer whitespace-nowrap"
          onClick={() => navigate("/")}
        >
          BeeWork
        </h1>
        <div className="flex-1 mx-4 overflow-hidden">
          <p className="font-mono text-xs text-primary-foreground/80 truncate text-left h-5 leading-5">
            {line}
          </p>
        </div>
        <SettingsDialog />
      </nav>
    </div>
  );
}

function StatCard({ label, active, total }: { label: string; active: number; total: number }) {
  return (
    <div className="border border-border bg-background px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-bold">
        {active > 0 ? <span className="text-bee-yellow">{active}</span> : "0"}
        <span className="text-muted-foreground text-sm font-normal"> / {total}</span>
      </p>
    </div>
  );
}
