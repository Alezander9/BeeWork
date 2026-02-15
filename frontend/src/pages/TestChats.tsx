import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAction } from "convex/react";
import { api } from "../../convex/_generated/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import SettingsDialog from "@/components/SettingsDialog";
import { getAdminToken } from "@/lib/auth";

export default function TestChats() {
  const navigate = useNavigate();
  const chat = useAction(api.chat.chat);

  const [repo, setRepo] = useState("workerbee-gbt/medical");
  const [model, setModel] = useState("google/gemini-3-flash");
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [withKB, setWithKB] = useState<{ response: string | null; error: string | null }>({ response: null, error: null });
  const [withoutKB, setWithoutKB] = useState<{ response: string | null; error: string | null }>({ response: null, error: null });

  async function handleSend() {
    const secret = getAdminToken();
    if (!secret) {
      alert("Set your admin credentials first (bee icon, bottom-right).");
      return;
    }
    if (!prompt.trim()) return;

    setLoading(true);
    setWithKB({ response: null, error: null });
    setWithoutKB({ response: null, error: null });

    const base = { repo: repo.trim(), prompt: prompt.trim(), model: model.trim(), secret };

    const [kbResult, plainResult] = await Promise.allSettled([
      chat({ ...base, useKnowledgebase: true }),
      chat({ ...base, useKnowledgebase: false }),
    ]);

    setWithKB(
      kbResult.status === "fulfilled"
        ? { response: kbResult.value, error: null }
        : { response: null, error: kbResult.reason instanceof Error ? kbResult.reason.message : "Request failed" },
    );
    setWithoutKB(
      plainResult.status === "fulfilled"
        ? { response: plainResult.value, error: null }
        : { response: null, error: plainResult.reason instanceof Error ? plainResult.reason.message : "Request failed" },
    );

    setLoading(false);
  }

  return (
    <div className="min-h-screen bg-background/50 pb-16">
      <main className="max-w-6xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold mb-6">Test Chat</h2>

        <div className="flex flex-col gap-4">
          {/* Repo + Model + Send row */}
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <Label className="text-xs text-muted-foreground mb-1">Repository</Label>
              <Input
                placeholder="owner/repo"
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
            <div className="flex-1">
              <Label className="text-xs text-muted-foreground mb-1">Model</Label>
              <Input
                placeholder="provider/model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
            <Button onClick={handleSend} disabled={loading || !prompt.trim()} className="shrink-0">
              {loading ? "Thinking..." : "Send to both"}
            </Button>
          </div>

          {/* Prompt */}
          <div>
            <Label className="text-xs text-muted-foreground mb-1">Prompt</Label>
            <textarea
              placeholder="Ask something..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSend();
              }}
              rows={4}
              className="placeholder:text-muted-foreground border-input w-full rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] resize-y"
            />
            <p className="text-xs text-muted-foreground mt-1">Ctrl+Enter to send</p>
          </div>
        </div>

        {/* Side-by-side responses */}
        {(loading || withKB.response || withKB.error || withoutKB.response || withoutKB.error) && (
          <div className="grid grid-cols-2 gap-4 mt-6">
            <ResponsePanel
              title="With Knowledgebase"
              loading={loading}
              response={withKB.response}
              error={withKB.error}
            />
            <ResponsePanel
              title="Without Knowledgebase"
              loading={loading}
              response={withoutKB.response}
              error={withoutKB.error}
            />
          </div>
        )}
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

function ResponsePanel({
  title,
  loading,
  response,
  error,
}: {
  title: string;
  loading: boolean;
  response: string | null;
  error: string | null;
}) {
  return (
    <div className="border border-border bg-background p-4 min-h-[200px]">
      <p className="text-xs font-medium text-muted-foreground mb-3">{title}</p>
      {loading && !response && !error && (
        <p className="text-sm text-muted-foreground">Thinking...</p>
      )}
      {error && (
        <p className="text-sm text-destructive whitespace-pre-wrap">{error}</p>
      )}
      {response && (
        <div className="text-sm whitespace-pre-wrap">{response}</div>
      )}
    </div>
  );
}
