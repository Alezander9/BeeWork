import { useNavigate } from "react-router-dom";
import SettingsDialog from "@/components/SettingsDialog";

const DUMMY_SESSIONS = [
  { id: "a1b2c3", repo: "california-rng", tasks: 4, status: "completed", date: "2026-02-14" },
  { id: "d4e5f6", repo: "tiny-test", tasks: 2, status: "in_progress", date: "2026-02-14" },
  { id: "g7h8i9", repo: "small-test", tasks: 3, status: "failed", date: "2026-02-13" },
];

const STATUS_STYLES: Record<string, string> = {
  completed: "text-green-700 bg-green-100",
  in_progress: "text-bee-yellow bg-secondary",
  failed: "text-destructive bg-red-50",
};

export default function Sessions() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background/90">
      <header className="border-b border-border px-6 py-4 flex items-center justify-between bg-background">
        <h1
          className="text-lg font-bold tracking-tight cursor-pointer"
          onClick={() => navigate("/")}
        >
          BeeWork
        </h1>
        <SettingsDialog />
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold mb-6">Sessions</h2>

        <div className="border border-border">
          <div className="grid grid-cols-[1fr_80px_120px_100px] gap-4 px-4 py-2 text-sm font-medium text-muted-foreground border-b border-border">
            <span>Repository</span>
            <span>Tasks</span>
            <span>Status</span>
            <span>Date</span>
          </div>

          {DUMMY_SESSIONS.map((session) => (
            <div
              key={session.id}
              className="grid grid-cols-[1fr_80px_120px_100px] gap-4 px-4 py-3 text-sm border-b border-border last:border-b-0 hover:bg-secondary/50 cursor-pointer transition-colors"
              onClick={() => navigate(`/sessions/${session.id}`)}
            >
              <span className="font-medium">{session.repo}</span>
              <span>{session.tasks}</span>
              <span>
                <span className={`px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[session.status] ?? ""}`}>
                  {session.status.replace("_", " ")}
                </span>
              </span>
              <span className="text-muted-foreground">{session.date}</span>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
