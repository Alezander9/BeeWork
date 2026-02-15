import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "convex/react";
import { motion } from "motion/react";
import { Check, CircleDashed, Loader2 } from "lucide-react";
import { api } from "../../convex/_generated/api";
import type { Id } from "../../convex/_generated/dataModel";
import SettingsDialog from "@/components/SettingsDialog";
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
  if (status === "running") return <Loader2 className="w-4 h-4 text-bee-yellow animate-spin" />;
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
            className="absolute inset-0 w-full h-full"
            sandbox="allow-scripts allow-same-origin"
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

// --- Component ---

export default function NewSessionView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const sessionId = id as Id<"sessions">;

  const logs = useQuery(api.sessions.getSessionLogs, { sessionId });
  const events = useQuery(api.sessions.getSessionEvents, { sessionId });
  const { line, push } = useLogTicker();
  const orchSteps = useOrchSteps(events);
  const workers = useWorkers(events);

  const orchDone = orchAllDone(orchSteps);
  const pipelineStarted = events?.some((e) => e.type === "pipeline_started") ?? false;
  const pipelineDone = events?.some((e) => e.type === "pipeline_done") ?? false;

  const activeColumns = useMemo(() => ({
    Orchestrator: pipelineStarted && !orchDone,
    Workers: orchDone && !pipelineDone,
    Reviewers: false,
    Github: false,
  }), [pipelineStarted, orchDone, pipelineDone]);

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
    <div className="h-screen bg-background/50 pb-16 flex flex-col overflow-hidden">
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
          <BeePanel label="Orchestrator" active={activeColumns["Orchestrator"]}>
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
          <BeePanel label="Workers" active={activeColumns["Workers"]}>
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
          className="min-w-0 flex flex-col items-center p-4 overflow-y-auto"
        >
          <BeePanel label="Reviewers" active={activeColumns["Reviewers"]} fill>
            <p className="text-xs text-muted-foreground">Reviewer content here</p>
          </BeePanel>
        </motion.div>

        <div className="w-px h-48 bg-foreground/15 self-center shrink-0" />

        {/* Column 4: Github */}
        <motion.div
          animate={{ flex: activeColumns["Github"] ? COLUMN_FOCUS_FLEX["Github"] : 1, width: "auto" }}
          transition={spring}
          className="p-4 min-w-0 flex flex-col items-center justify-center overflow-y-auto"
        >
          <p className="text-sm font-bold">Github</p>
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
