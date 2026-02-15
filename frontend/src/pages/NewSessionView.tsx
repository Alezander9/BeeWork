import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useAction } from "convex/react";
import { motion } from "motion/react";
import { Check, Circle, CircleDashed } from "lucide-react";
import { api } from "../../convex/_generated/api";
import type { Id } from "../../convex/_generated/dataModel";
import SettingsDialog from "@/components/SettingsDialog";
import ChatOverlay from "@/components/ChatOverlay";
import beePng from "@/assets/bee.png";

// --- Log ticker ---

function useLogTicker() {
  const [line, setLine] = useState("");
  const queue = useRef<string[]>([]);
  const running = useRef(false);

  function nextDelay() {
    const pending = queue.current.length;
    const mean = Math.max(40, 400 / (1 + pending * 0.3));
    return -mean * Math.log(Math.random() || 0.001);
  }

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
      setTimeout(tick, nextDelay());
    })();
  }

  const push = useCallback((...lines: string[]) => {
    queue.current.push(...lines);
    flush();
  }, []);

  return { line, push };
}

// --- Orchestrator steps ---

const ORCH_STEPS = [
  { event: "sandbox_created", label: "Sandbox created" },
  { event: "repo_created", label: "Repository created" },
  { event: "project_read", label: "Project read" },
  { event: "structure_built", label: "Structure built" },
  { event: "research_tasks_created", label: "Research tasks created" },
  { event: "changes_pushed", label: "Changes pushed" },
  { event: "research_agents_started", label: "Agents started" },
] as const;

type StepStatus = "pending" | "running" | "done";

function useOrchSteps(events: { type: string; data: Record<string, unknown> }[] | undefined) {
  return useMemo(() => {
    const seen = new Set<string>();
    let pipelineStarted = false;
    if (events) {
      for (const e of events) {
        seen.add(e.type);
        if (e.type === "pipeline_started") pipelineStarted = true;
      }
    }

    let foundFirstPending = false;
    return ORCH_STEPS.map((step) => {
      if (seen.has(step.event)) {
        return { ...step, status: "done" as StepStatus };
      }
      if (pipelineStarted && !foundFirstPending) {
        foundFirstPending = true;
        return { ...step, status: "running" as StepStatus };
      }
      return { ...step, status: "pending" as StepStatus };
    });
  }, [events]);
}

function orchAllDone(steps: { status: StepStatus }[]) {
  return steps.length > 0 && steps.every((s) => s.status === "done");
}

// --- Worker state from events ---

interface WorkerInfo {
  agentId: string;
  topic?: string;
  status: "running" | "done";
  phase: "waiting" | "browsing" | "creating_pr" | "done";
  browserUrl?: string;
  browserActive: boolean;
  judgeVerdict?: string;
  pr?: number;
}

// browser events use "slug:" as agent tag, researcher events use "slug"
function normAgent(raw: string) {
  return raw.endsWith(":") ? raw.slice(0, -1) : raw;
}

function useWorkers(events: { type: string; data: Record<string, unknown> }[] | undefined) {
  return useMemo(() => {
    const map = new Map<string, WorkerInfo>();
    if (!events) return [];
    for (const e of events) {
      const d = e.data as Record<string, unknown>;
      switch (e.type) {
        case "researcher_started":
          map.set(d.agent_id as string, {
            agentId: d.agent_id as string,
            topic: d.topic as string | undefined,
            status: "running",
            phase: "waiting",
            browserActive: false,
          });
          break;
        case "browser_url": {
          const w = map.get(normAgent(d.agent as string));
          if (w) {
            w.browserUrl = d.url as string;
            w.browserActive = true;
            w.phase = "browsing";
          }
          break;
        }
        case "browser_done": {
          const w = map.get(normAgent(d.agent as string));
          if (w) {
            w.browserActive = false;
            w.phase = "creating_pr";
          }
          break;
        }
        case "browser_judge_done": {
          const w = map.get(normAgent(d.agent as string));
          if (w) w.judgeVerdict = d.verdict as string;
          break;
        }
        case "pr_created": {
          const w = map.get(d.agent_id as string);
          if (w) w.pr = d.pr as number;
          break;
        }
        case "researcher_done": {
          const w = map.get(d.agent_id as string);
          if (w) {
            w.status = "done";
            w.phase = "done";
            w.browserActive = false;
          }
          break;
        }
      }
    }
    const list = Array.from(map.values());
    list.sort((a, b) => {
      if (a.status === b.status) return 0;
      return a.status === "running" ? -1 : 1;
    });
    return list;
  }, [events]);
}

// --- PR state from events ---

interface PRInfo {
  pr: number;
  agentId: string;
  repo?: string;
  topic?: string;
  status: "pending" | "reviewing" | "merged" | "closed" | "open";
}

function usePRs(events: { type: string; data: Record<string, unknown> }[] | undefined) {
  return useMemo(() => {
    const map = new Map<number, PRInfo>();
    if (!events) return [];
    for (const e of events) {
      const d = e.data as Record<string, unknown>;
      switch (e.type) {
        case "pr_created":
          map.set(d.pr as number, {
            pr: d.pr as number,
            agentId: d.agent_id as string,
            repo: d.repo as string | undefined,
            topic: d.topic as string | undefined,
            status: "pending",
          });
          break;
        case "reviewer_started": {
          const existing = map.get(d.pr as number);
          if (existing) existing.status = "reviewing";
          break;
        }
        case "pr_reviewed": {
          const existing = map.get(d.pr as number);
          if (existing) {
            const state = d.state as string;
            if (state === "merged" || state === "closed" || state === "open")
              existing.status = state;
          }
          break;
        }
      }
    }
    return Array.from(map.values());
  }, [events]);
}

// --- Layout ---

const COLUMN_FOCUS_FLEX: Record<string, number> = {
  Orchestrator: 2,
  Workers: 3,
  Reviewers: 2,
  Github: 2,
};

const spring = { type: "spring" as const, stiffness: 300, damping: 30 };

const beeAnim = {
  active: {
    rotate: [0, -15, 0, 15, 0],
    y: [0, -20, 0, -20, 0],
  },
  idle: { rotate: 0, y: 0 },
};

const beeTransition = {
  active: {
    duration: 1.6,
    repeat: Infinity,
    repeatDelay: 0,
    ease: "easeInOut" as const,
    times: [0, 0.25, 0.5, 0.75, 1],
  },
  idle: { duration: 0.3 },
};

// --- Step icon ---

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "done") return <Check className="w-4 h-4 text-green-700" />;
  if (status === "running") return <Circle className="w-4 h-4 text-bee-yellow" />;
  return <CircleDashed className="w-4 h-4 text-muted-foreground/50" />;
}

// --- Panel with bee icon ---

function BeePanel({
  label,
  active,
  fill = false,
  children,
}: {
  label: string;
  active: boolean;
  fill?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <>
      <div className={`relative w-full min-h-[160px] ${fill ? "flex-1" : ""}`}>
        <motion.img
          src={beePng}
          alt=""
          animate={active ? beeAnim.active : beeAnim.idle}
          transition={active ? beeTransition.active : beeTransition.idle}
          className="absolute -left-3 -bottom-3 w-14 h-14 -scale-x-100 pointer-events-none z-20"
        />
        <div className="border border-border bg-background w-full h-full overflow-y-auto p-3">
          {children}
        </div>
      </div>
      <p className="text-sm font-bold mt-3 shrink-0">{label}</p>
    </>
  );
}

// --- Worker card ---

const WORKER_WIDTH = 220;
const IFRAME_INTERNAL_W = 1100;
const IFRAME_INTERNAL_H = 620;
const IFRAME_SCALE = WORKER_WIDTH / IFRAME_INTERNAL_W;

function WorkerCard({ worker }: { worker: WorkerInfo }) {
  return (
    <div style={{ width: WORKER_WIDTH }} className="shrink-0">
      <p className="text-xs text-muted-foreground mb-1 truncate" title={worker.agentId}>
        {worker.topic ?? worker.agentId}
      </p>
      <div className="w-full aspect-video border border-bee-yellow overflow-hidden relative">
        {worker.phase === "browsing" && worker.browserUrl ? (
          <iframe
            src={worker.browserUrl}
            sandbox="allow-scripts allow-same-origin"
            style={{
              width: IFRAME_INTERNAL_W,
              height: IFRAME_INTERNAL_H,
              transform: `scale(${IFRAME_SCALE})`,
              transformOrigin: "top left",
            }}
          />
        ) : worker.phase === "creating_pr" ? (
          <div className="w-full h-full flex flex-col items-center justify-center bg-secondary gap-1">
            <p className="text-xs text-foreground">
              Browser agent: {worker.judgeVerdict ?? "..."}
            </p>
            <p className="text-xs text-bee-yellow">Creating PR...</p>
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-secondary">
            <p className="text-xs text-bee-yellow">waiting for browser...</p>
          </div>
        )}
      </div>
    </div>
  );
}

// --- PR status badge ---

const PR_STATUS_STYLE: Record<string, string> = {
  pending: "bg-muted text-muted-foreground",
  reviewing: "bg-secondary text-bee-yellow",
  merged: "bg-secondary text-green-700",
  closed: "bg-secondary text-destructive",
  open: "bg-secondary text-foreground",
};

function PRStatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-0.5 text-xs font-medium ${PR_STATUS_STYLE[status] ?? PR_STATUS_STYLE.pending}`}>
      {status}
    </span>
  );
}

// --- File tree ---

interface TreeNode {
  name: string;
  children: TreeNode[];
}

function buildTree(entries: { path: string; type: string }[]): TreeNode[] {
  const root: TreeNode[] = [];
  for (const entry of entries) {
    if (entry.type !== "blob") continue;
    const parts = entry.path.split("/");
    let level = root;
    for (let i = 0; i < parts.length; i++) {
      const name = parts[i];
      let existing = level.find((n) => n.name === name);
      if (!existing) {
        existing = { name, children: [] };
        level.push(existing);
      }
      level = existing.children;
    }
  }
  return root;
}

function FileTree({ entries }: { entries: { path: string; type: string }[] }) {
  const tree = useMemo(() => buildTree(entries), [entries]);
  return (
    <ul className="text-xs font-mono pb-10 text-foreground">
      {tree.map((node, i) => (
        <TreeNodeRow key={node.name} node={node} isLast={i === tree.length - 1} prefix="" />
      ))}
    </ul>
  );
}

function TreeNodeRow({ node, isLast, prefix }: { node: TreeNode; isLast: boolean; prefix: string }) {
  const isDir = node.children.length > 0;
  const [open, setOpen] = useState(true);
  const connector = isLast ? "\u2514\u2500\u2500 " : "\u251C\u2500\u2500 ";
  const childPrefix = prefix + (isLast ? "    " : "\u2502   ");
  return (
    <li>
      <div
        className={`whitespace-pre leading-5 ${isDir ? "cursor-pointer font-bold" : ""}`}
        onClick={isDir ? () => setOpen(!open) : undefined}
      >
        {prefix}{connector}{node.name}{isDir ? "/" : ""}
      </div>
      {isDir && open && (
        <ul>
          {node.children.map((child, i) => (
            <TreeNodeRow key={child.name} node={child} isLast={i === node.children.length - 1} prefix={childPrefix} />
          ))}
        </ul>
      )}
    </li>
  );
}

// --- Component ---

export default function NewSessionView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const sessionId = id as Id<"sessions">;

  const session = useQuery(api.sessions.getSession, { sessionId });
  const logs = useQuery(api.sessions.getSessionLogs, { sessionId });
  const events = useQuery(api.sessions.getSessionEvents, { sessionId });
  const repoTree = useQuery(api.sessions.getRepoTree, { sessionId });
  const sessionComplete = session?.status === "completed" || session?.status === "failed";
  const fetchTree = useAction(api.sessions.fetchRepoTree);
  const { line, push } = useLogTicker();
  const orchSteps = useOrchSteps(events);
  const workers = useWorkers(events);

  const prs = usePRs(events);

  // Poll GitHub tree every 5s while mounted
  useEffect(() => {
    fetchTree({ sessionId }).catch(() => {});
    const id = setInterval(() => fetchTree({ sessionId }).catch(() => {}), 5000);
    return () => clearInterval(id);
  }, [sessionId, fetchTree]);

  const orchDone = orchAllDone(orchSteps);
  const pipelineStarted = events?.some((e) => e.type === "pipeline_started") ?? false;
  const allWorkersDone = workers.length > 0 && workers.every((w) => w.status === "done");
  const hasActiveReviewers = prs.some((p) => p.status === "reviewing");

  const activeColumns = useMemo(() => ({
    Orchestrator: pipelineStarted && !orchDone,
    Workers: orchDone && !allWorkersDone,
    Reviewers: hasActiveReviewers,
    Github: false,
  }), [pipelineStarted, orchDone, allWorkersDone, hasActiveReviewers]);

  const seenLogs = useRef(0);
  useEffect(() => {
    if (!logs || sessionComplete) return;
    if (logs.length > seenLogs.current) {
      const newBatches = logs.slice(seenLogs.current);
      seenLogs.current = logs.length;
      const lines = newBatches.flatMap((b) => b.text.split("\n").filter(Boolean));
      push(...lines);
    }
  }, [logs, push, sessionComplete]);

  return (
    <div className="h-screen bg-background/50 pb-16 flex flex-col overflow-hidden">
      <ChatOverlay defaultRepo={repoTree?.repo} />
      {/* Top bar: breadcrumb */}
      <header className="w-full px-6 py-4">
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
      </header>

      {/* Four-column content area */}
      <main className="flex-1 min-h-0 px-6 flex items-stretch">
        {/* Column 1: Orchestrator */}
        <motion.div
          animate={{ flex: activeColumns["Orchestrator"] ? COLUMN_FOCUS_FLEX["Orchestrator"] : 1, width: "auto" }}
          transition={spring}
          className="min-w-0 flex flex-col items-center justify-center p-4 overflow-y-auto"
        >
          <BeePanel label="Queen Bee" active={activeColumns["Orchestrator"]}>
            <ul className="space-y-2 pb-10">
              {orchSteps.map((step) => (
                <li key={step.event} className="flex items-center justify-between gap-2 text-sm">
                  <span className={step.status === "pending" ? "text-muted-foreground/50" : "text-foreground"}>
                    {step.label}
                  </span>
                  <StepIcon status={step.status} />
                </li>
              ))}
            </ul>
          </BeePanel>
        </motion.div>

        <div className="w-px h-48 bg-foreground/15 self-center shrink-0" />

        {/* Column 2: Workers */}
        <motion.div
          animate={{ flex: activeColumns["Workers"] ? COLUMN_FOCUS_FLEX["Workers"] : 1, width: "auto" }}
          transition={spring}
          className="min-w-0 flex flex-col items-center justify-center p-4 overflow-y-auto"
        >
          <BeePanel label="Forager Bees" active={activeColumns["Workers"]}>
            {workers.length === 0 ? (
              <p className="text-xs text-muted-foreground">No workers yet</p>
            ) : (
              <>
                <div className="flex flex-wrap gap-3 justify-center">
                  {workers.filter((w) => w.status === "running").map((w) => (
                    <WorkerCard key={w.agentId} worker={w} />
                  ))}
                </div>
                {workers.some((w) => w.status === "done") && (
                  <div className="mt-3 pt-2 pb-10 border-t border-foreground/30">
                    <p className="text-xs text-muted-foreground mb-1">Completed Workers:</p>
                    <ul className="space-y-0.5">
                      {workers.filter((w) => w.status === "done").map((w) => (
                        <li key={w.agentId} className="text-xs text-muted-foreground/70">
                          {w.topic ?? w.agentId}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </BeePanel>
        </motion.div>

        <div className="w-px h-48 bg-foreground/15 self-center shrink-0" />

        {/* Column 3: Reviewers */}
        <motion.div
          animate={{ flex: activeColumns["Reviewers"] ? COLUMN_FOCUS_FLEX["Reviewers"] : 1, width: "auto" }}
          transition={spring}
          className="min-w-0 flex flex-col items-center justify-center p-4 overflow-y-auto"
        >
          <BeePanel label="House Bees" active={activeColumns["Reviewers"]}>
            {prs.length === 0 ? (
              <p className="text-xs text-muted-foreground">No PRs yet</p>
            ) : (
              <ul className="divide-y divide-border pb-10">
                {prs.map((pr) => (
                  <li key={pr.pr} className="flex items-center justify-between gap-2 py-2 text-sm">
                    <span className="truncate">
                      <span className="font-mono">#{pr.pr}</span>{" "}
                      <span className="text-muted-foreground">{pr.topic ?? pr.agentId}</span>
                    </span>
                    <div className="flex items-center gap-2 shrink-0">
                      <PRStatusBadge status={pr.status} />
                      {pr.repo && (
                        <a
                          href={`https://github.com/${pr.repo}/pull/${pr.pr}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-accent hover:underline text-xs"
                        >
                          link
                        </a>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </BeePanel>
        </motion.div>

        <div className="w-px h-48 bg-foreground/15 self-center shrink-0" />

        {/* Column 4: Github */}
        <motion.div
          animate={{ flex: activeColumns["Github"] ? COLUMN_FOCUS_FLEX["Github"] : 1, width: "auto" }}
          transition={spring}
          className="p-4 min-w-0 flex flex-col items-center justify-center overflow-y-auto"
        >
          <div className="w-full min-h-[160px] bg-background overflow-y-auto p-3">
            {repoTree?.repo && (
              <div className="flex items-center gap-3 mb-3">
                <span className="text-sm font-mono font-bold text-foreground">
                  github.com/{repoTree.repo}
                </span>
                <a
                  href={`https://github.com/${repoTree.repo}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-accent hover:underline"
                >
                  link
                </a>
              </div>
            )}
            {!repoTree ? (
              <p className="text-sm text-muted-foreground">Loading tree...</p>
            ) : repoTree.tree.length === 0 ? (
              <p className="text-sm text-muted-foreground">Empty repository</p>
            ) : (
              <FileTree entries={repoTree.tree} />
            )}
          </div>
        </motion.div>
      </main>

      {/* Bottom bar with log ticker */}
      <nav className="fixed bottom-0 left-0 right-0 border-t-3 border-bee-black bg-primary px-6 py-3 flex items-center justify-between">
        <h1
          className="text-lg font-bold tracking-tight text-primary-foreground cursor-pointer whitespace-nowrap"
          onClick={() => navigate("/")}
        >
          BeeWork
        </h1>
        <div className="flex-1 mx-4 overflow-hidden">
          <p className="font-mono text-lg text-primary-foreground/80 truncate text-left h-6 leading-6">
            {line}
          </p>
        </div>
        <SettingsDialog />
      </nav>
    </div>
  );
}
