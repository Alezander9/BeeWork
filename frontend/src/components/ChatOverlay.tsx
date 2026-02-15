import { useState, useEffect, useRef } from "react";
import { useAction } from "convex/react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { api } from "../../convex/_generated/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getAdminToken } from "@/lib/auth";

const PROMPT_PRESETS = [
  { name: "Medical", prompt: "Which complement proteins tag weak synapses for elimination in the context of Alzheimers disease" },
];

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
    <div className="border border-border bg-background p-4 min-h-0 flex-1 overflow-y-auto">
      <p className="text-lg font-bold text-muted-foreground mb-3">{title}</p>
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

export default function ChatOverlay({ defaultRepo }: { defaultRepo?: string }) {
  const chat = useAction(api.chat.chat);

  const [open, setOpen] = useState(false);
  const [repo, setRepo] = useState(defaultRepo ?? "");
  const [model, setModel] = useState("google/gemini-3-flash");

  // Update repo when defaultRepo resolves async
  useEffect(() => {
    if (defaultRepo && !repo) setRepo(defaultRepo);
  }, [defaultRepo]);
  const [prompt, setPrompt] = useState("");
  const [presetsOpen, setPresetsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  type Result = { response: string | null; error: string | null };
  const empty: Result = { response: null, error: null };
  const [withKB, setWithKB] = useState<Result>(empty);
  const [withSearch, setWithSearch] = useState<Result>(empty);
  const [plain, setPlain] = useState<Result>(empty);

  const pending = useRef(0);

  async function handleSend() {
    const secret = getAdminToken();
    if (!secret) {
      alert("Set your admin credentials first (bee icon, bottom-right).");
      return;
    }
    if (!prompt.trim()) return;

    setLoading(true);
    setWithKB(empty);
    setWithSearch(empty);
    setPlain(empty);
    pending.current = 3;

    const base = { repo: repo.trim(), prompt: prompt.trim(), model: model.trim(), secret };

    function done(setter: typeof setWithKB, r: string | Error) {
      setter(r instanceof Error ? { response: null, error: r.message } : { response: r, error: null });
      pending.current--;
      if (pending.current === 0) setLoading(false);
    }

    chat({ ...base, mode: "kb" }).then((r) => done(setWithKB, r)).catch((e) => done(setWithKB, e instanceof Error ? e : new Error("Request failed")));
    chat({ ...base, mode: "search" }).then((r) => done(setWithSearch, r)).catch((e) => done(setWithSearch, e instanceof Error ? e : new Error("Request failed")));
    chat({ ...base, mode: "plain" }).then((r) => done(setPlain, r)).catch((e) => done(setPlain, e instanceof Error ? e : new Error("Request failed")));
  }

  const hasResults = loading || withKB.response || withKB.error || withSearch.response || withSearch.error || plain.response || plain.error;

  return (
    <>
      {/* Pull-down tab (visible when closed) */}
      <AnimatePresence>
        {!open && (
          <motion.button
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            onClick={() => setOpen(true)}
            className="fixed top-0 right-12 z-50 px-10 py-0 bg-white text-black border-2 border-t-0 rounded-b-xl cursor-pointer transition-shadow hover:shadow-[0_0_14px_3px_rgba(234,179,8,0.25)]"
          >
            <ChevronDown className="w-5 h-5" />
          </motion.button>
        )}
      </AnimatePresence>

      {/* Sliding panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ y: "-100%" }}
            animate={{ y: 0 }}
            exit={{ y: "-100%" }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="fixed top-0 left-0 right-0 z-40 bg-background/95 backdrop-blur-sm border-b border-border shadow-lg flex flex-col"
            style={{ height: "80vh" }}
          >
            <div className="flex-1 min-h-0 flex flex-col px-6 py-6 overflow-hidden">
              <h2 className="text-xl font-bold mb-4">Chat GBT</h2>

              {/* Repo + Model + Send row */}
              <div className="flex gap-3 items-end mb-4">
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
                  {loading ? "Thinking..." : "Send to all"}
                </Button>
              </div>

              {/* Prompt */}
              <div className="mb-4">
                <div className="flex items-center gap-2 mb-1">
                  <Label className="text-xs text-muted-foreground">Prompt</Label>
                  <div className="relative">
                    <button
                      onClick={() => setPresetsOpen(!presetsOpen)}
                      className="text-xs text-muted-foreground cursor-pointer hover:text-foreground transition-colors"
                    >
                      saved
                    </button>
                    {presetsOpen && (
                      <div className="absolute top-6 left-0 z-50 w-64 border border-border bg-background shadow-lg rounded-md py-1">
                        {PROMPT_PRESETS.map((p) => (
                          <button
                            key={p.name}
                            onClick={() => { setPrompt(p.prompt); setPresetsOpen(false); }}
                            className="w-full text-left px-3 py-2 text-sm hover:bg-secondary transition-colors"
                          >
                            {p.name}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <textarea
                  placeholder="Ask something..."
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSend();
                  }}
                  rows={3}
                  className="placeholder:text-muted-foreground border-input w-full rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] resize-none"
                />
                <p className="text-xs text-muted-foreground mt-1">Ctrl+Enter to send</p>
              </div>

              {/* Side-by-side responses */}
              {hasResults && (
                <div className="grid grid-cols-3 gap-4 flex-1 min-h-0">
                  <ResponsePanel
                    title="With Knowledgebase"
                    loading={loading}
                    response={withKB.response}
                    error={withKB.error}
                  />
                  <ResponsePanel
                    title="With Search"
                    loading={loading}
                    response={withSearch.response}
                    error={withSearch.error}
                  />
                  <ResponsePanel
                    title="Without Knowledgebase"
                    loading={loading}
                    response={plain.response}
                    error={plain.error}
                  />
                </div>
              )}
            </div>

          </motion.div>
        )}
      </AnimatePresence>

      {/* Close tab - rendered outside the panel so glow doesn't overlap */}
      <AnimatePresence>
        {open && (
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={() => setOpen(false)}
            className="fixed left-1/2 -translate-x-1/2 z-30 px-10 py-0 bg-white text-black border-2 border-t-0 rounded-b-xl cursor-pointer transition-shadow hover:shadow-[0_0_14px_3px_rgba(234,179,8,0.25)]"
            style={{ top: "80vh" }}
          >
            <ChevronUp className="w-5 h-5" />
          </motion.button>
        )}
      </AnimatePresence>
    </>
  );
}
