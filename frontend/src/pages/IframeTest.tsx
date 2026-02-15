import { useState } from "react";

const PLACEHOLDER = "PASTE_LIVE_URL_HERE";

export default function IframeTest() {
  const [url, setUrl] = useState(PLACEHOLDER);
  const [submitted, setSubmitted] = useState(false);

  return (
    <div className="min-h-screen bg-background p-8 flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Iframe Embed Test</h1>

      <div className="flex gap-2">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Paste a liveUrl here"
          className="flex-1 border border-border bg-background px-3 py-2 text-sm font-mono"
        />
        <button
          onClick={() => setSubmitted(true)}
          className="px-4 py-2 bg-bee-yellow text-bee-black text-sm font-bold"
        >
          Load
        </button>
      </div>

      {submitted && url && url !== PLACEHOLDER && (
        <div className="flex flex-col gap-4">
          <div>
            <p className="text-sm text-muted-foreground mb-1">Full size (800x600)</p>
            <iframe
              src={url}
              className="w-[800px] h-[600px] border border-border"
              sandbox="allow-scripts allow-same-origin"
            />
          </div>
          <div>
            <p className="text-sm text-muted-foreground mb-1">Small (400x300)</p>
            <iframe
              src={url}
              className="w-[400px] h-[300px] border border-border"
              sandbox="allow-scripts allow-same-origin"
            />
          </div>
          <div>
            <p className="text-sm text-muted-foreground mb-1">Tiny (200x150)</p>
            <iframe
              src={url}
              className="w-[200px] h-[150px] border border-border"
              sandbox="allow-scripts allow-same-origin"
            />
          </div>
        </div>
      )}

      {!submitted && (
        <p className="text-sm text-muted-foreground">
          Paste a browser-use liveUrl into the input above and click Load to test if it can be embedded.
        </p>
      )}
    </div>
  );
}
