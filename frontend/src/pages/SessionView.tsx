import { useParams, useNavigate } from "react-router-dom";
import SettingsDialog from "@/components/SettingsDialog";

export default function SessionView() {
  const { id } = useParams();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background/50 pb-16">
      <main className="max-w-3xl mx-auto px-6 py-10">
        <div className="flex items-center gap-2 mb-6 text-sm">
          <span
            className="text-muted-foreground cursor-pointer hover:text-foreground transition-colors"
            onClick={() => navigate("/sessions")}
          >
            Sessions
          </span>
          <span className="text-muted-foreground">/</span>
          <span className="font-mono">{id}</span>
        </div>
        <p className="text-muted-foreground">Session detail view -- coming soon.</p>
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
