import { useParams, useNavigate } from "react-router-dom";
import SettingsDialog from "@/components/SettingsDialog";

export default function SessionView() {
  const { id } = useParams();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background/90">
      <header className="border-b border-border px-6 py-4 flex items-center justify-between bg-background">
        <div className="flex items-center gap-4">
          <h1
            className="text-lg font-bold tracking-tight cursor-pointer"
            onClick={() => navigate("/")}
          >
            BeeWork
          </h1>
          <span className="text-muted-foreground">/</span>
          <span
            className="text-sm text-muted-foreground cursor-pointer hover:text-foreground transition-colors"
            onClick={() => navigate("/sessions")}
          >
            Sessions
          </span>
          <span className="text-muted-foreground">/</span>
          <span className="text-sm font-mono">{id}</span>
        </div>
        <SettingsDialog />
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10">
        <p className="text-muted-foreground">Session detail view -- coming soon.</p>
      </main>
    </div>
  );
}
