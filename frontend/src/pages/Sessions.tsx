import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useAction } from "convex/react";
import { api } from "../../convex/_generated/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import SettingsDialog from "@/components/SettingsDialog";
import { getAdminToken } from "@/lib/auth";

const STATUS_STYLES: Record<string, string> = {
  completed: "text-green-700 bg-green-100",
  running: "text-bee-yellow bg-secondary",
  pending: "text-muted-foreground bg-muted",
  failed: "text-destructive bg-red-50",
};

export default function Sessions() {
  const navigate = useNavigate();
  const sessions = useQuery(api.sessions.listSessions);
  const startSession = useAction(api.sessions.startSession);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [repo, setRepo] = useState("");
  const [project, setProject] = useState("shared/project_documents/tiny_test.md");
  const [researchWorkers, setResearchWorkers] = useState(15);
  const [reviewWorkers, setReviewWorkers] = useState(3);

  async function handleCreate() {
    const secret = getAdminToken();
    if (!secret) {
      alert("Set your admin credentials first (bee icon, bottom-right).");
      return;
    }
    if (!repo.trim()) return;
    setLoading(true);
    try {
      const sessionId = await startSession({
        repo: repo.trim(),
        researchWorkers,
        reviewWorkers,
        project: project.trim(),
        secret,
      });
      console.log("[beework] session created", sessionId);
      setOpen(false);
      setRepo("");
      navigate(`/sessions/${sessionId}`);
    } catch (e: unknown) {
      console.error("[beework] session failed", e);
      alert(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background/50 pb-16">
      <main className="max-w-3xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold">Sessions</h2>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>New Session</Button>
            </DialogTrigger>
            <DialogContent className="max-w-sm">
              <DialogHeader>
                <DialogTitle>New Pipeline Session</DialogTitle>
              </DialogHeader>
              <div className="flex flex-col gap-3 pt-2">
                <Input
                  placeholder="Repository name"
                  value={repo}
                  onChange={(e) => setRepo(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                />
                <div>
                  <label className="text-xs text-muted-foreground">Project document</label>
                  <Input
                    placeholder="shared/project_documents/..."
                    value={project}
                    onChange={(e) => setProject(e.target.value)}
                    className="font-mono text-xs"
                  />
                </div>
                <div className="flex gap-3">
                  <div className="flex-1">
                    <label className="text-xs text-muted-foreground">Research workers</label>
                    <Input
                      type="number"
                      min={1}
                      value={researchWorkers}
                      onChange={(e) => setResearchWorkers(Number(e.target.value))}
                    />
                  </div>
                  <div className="flex-1">
                    <label className="text-xs text-muted-foreground">Review workers</label>
                    <Input
                      type="number"
                      min={1}
                      value={reviewWorkers}
                      onChange={(e) => setReviewWorkers(Number(e.target.value))}
                    />
                  </div>
                </div>
                <Button onClick={handleCreate} disabled={loading || !repo.trim()}>
                  {loading ? "Creating..." : "Start Pipeline"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        <div className="border border-border bg-background">
          <div className="grid grid-cols-[1fr_80px_120px_140px] gap-4 px-4 py-2 text-sm font-medium text-muted-foreground border-b border-border">
            <span>Repository</span>
            <span>Workers</span>
            <span>Status</span>
            <span>Created</span>
          </div>

          {sessions === undefined ? (
            <div className="px-4 py-6 text-sm text-muted-foreground text-center">Loading...</div>
          ) : sessions.length === 0 ? (
            <div className="px-4 py-6 text-sm text-muted-foreground text-center">No sessions yet</div>
          ) : (
            sessions.map((s) => (
              <div
                key={s._id}
                className="grid grid-cols-[1fr_80px_120px_140px] gap-4 px-4 py-3 text-sm border-b border-border last:border-b-0 hover:bg-secondary/50 cursor-pointer transition-colors"
                onClick={() => navigate(`/sessions/${s._id}`)}
              >
                <span className="font-medium">{s.repo}</span>
                <span>{s.researchWorkers + s.reviewWorkers}</span>
                <span>
                  <span className={`px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[s.status] ?? ""}`}>
                    {s.status}
                  </span>
                </span>
                <span className="text-muted-foreground">
                  {new Date(s.createdAt).toLocaleDateString()}
                </span>
              </div>
            ))
          )}
        </div>
      </main>

      <nav className="fixed bottom-0 left-0 right-0 border-t-3 border-bee-black bg-primary px-6 py-3 flex items-center justify-between">
        <h1
          className="text-lg font-bold tracking-tight text-primary-foreground cursor-pointer"
          onClick={() => navigate("/")}
        >
          BeeWork
        </h1>
        <SettingsDialog />
      </nav>
    </div>
  );
}
