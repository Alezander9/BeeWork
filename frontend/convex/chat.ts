import { v } from "convex/values";
import { action, internalMutation, internalQuery } from "./_generated/server";
import { internal } from "./_generated/api";

const SKIP_EXTS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
  ".woff", ".woff2", ".ttf", ".eot",
  ".pdf", ".zip", ".tar", ".gz", ".bz2",
  ".pyc", ".so", ".dll", ".exe",
  ".db", ".sqlite", ".sqlite3",
  ".lock", ".map",
]);

const SKIP_DIRS = new Set([
  "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".git",
]);

function shouldSkip(path: string): boolean {
  const parts = path.split("/");
  if (parts.some((p) => SKIP_DIRS.has(p))) return true;
  const dot = path.lastIndexOf(".");
  if (dot !== -1 && SKIP_EXTS.has(path.slice(dot).toLowerCase())) return true;
  return false;
}

const CACHE_TTL = 10 * 60 * 1000; // 10 minutes

// --- internal helpers ---

export const _getRepoCache = internalQuery({
  args: { repo: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("repoCache")
      .withIndex("by_repo", (q) => q.eq("repo", args.repo))
      .first();
  },
});

export const _upsertRepoCache = internalMutation({
  args: { repo: v.string(), flatText: v.string() },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("repoCache")
      .withIndex("by_repo", (q) => q.eq("repo", args.repo))
      .first();
    if (existing) {
      await ctx.db.patch(existing._id, { flatText: args.flatText, fetchedAt: Date.now() });
    } else {
      await ctx.db.insert("repoCache", {
        repo: args.repo,
        flatText: args.flatText,
        fetchedAt: Date.now(),
      });
    }
  },
});

// --- repo flattener ---

async function fetchAndFlatten(repo: string, pat?: string): Promise<string> {
  const headers: Record<string, string> = { Accept: "application/vnd.github+json" };
  if (pat) headers["Authorization"] = `Bearer ${pat}`;

  // get default branch
  const repoResp = await fetch(`https://api.github.com/repos/${repo}`, { headers });
  if (!repoResp.ok) {
    const body = await repoResp.text();
    throw new Error(`GitHub repo fetch failed (${repoResp.status}) for "${repo}" [PAT ${pat ? "set" : "missing"}]: ${body}`);
  }
  const { default_branch } = (await repoResp.json()) as { default_branch: string };

  // get recursive tree
  const treeResp = await fetch(
    `https://api.github.com/repos/${repo}/git/trees/${default_branch}?recursive=1`,
    { headers },
  );
  if (!treeResp.ok) throw new Error(`GitHub tree fetch failed (${treeResp.status})`);
  const { tree } = (await treeResp.json()) as { tree: { path: string; type: string; size?: number }[] };

  const blobs = tree.filter(
    (e) => e.type === "blob" && !shouldSkip(e.path) && (e.size ?? 0) < 200_000,
  );

  // fetch file contents in parallel (batches of 20)
  const parts: string[] = [];
  for (let i = 0; i < blobs.length; i += 20) {
    const batch = blobs.slice(i, i + 20);
    const results = await Promise.all(
      batch.map(async (blob) => {
        const url = `https://raw.githubusercontent.com/${repo}/${default_branch}/${blob.path}`;
        const resp = await fetch(url);
        if (!resp.ok) return null;
        const text = await resp.text();
        return `${"=".repeat(60)}\n FILE: ${blob.path}\n${"=".repeat(60)}\n${text}`;
      }),
    );
    for (const r of results) {
      if (r) parts.push(r);
    }
  }

  return parts.join("\n\n");
}

// --- main chat action ---
// mode: "plain" | "kb" | "search"

export const chat = action({
  args: {
    repo: v.string(),
    prompt: v.string(),
    model: v.string(),
    mode: v.string(),
    secret: v.string(),
  },
  returns: v.string(),
  handler: async (ctx, args) => {
    if (args.secret !== process.env.BEEWORK_SECRET_KEY) {
      throw new Error("unauthorized");
    }

    let systemPrompt = "You are a helpful assistant. Answer clearly and concisely.";

    if (args.mode === "kb") {
      const cached = await ctx.runQuery(internal.chat._getRepoCache, { repo: args.repo });
      let flatText: string;

      if (cached && Date.now() - cached.fetchedAt < CACHE_TTL) {
        flatText = cached.flatText;
      } else {
        flatText = await fetchAndFlatten(args.repo, process.env.GITHUB_PAT);
        await ctx.runMutation(internal.chat._upsertRepoCache, {
          repo: args.repo,
          flatText,
        });
      }

      systemPrompt =
        "You are a knowledgebase Q&A assistant. " +
        "Answer concisely. Do not repeat the question.\n" +
        "- When the knowledgebase contains relevant information, cite the file paths it came from.\n" +
        "- Prefer knowledgebase information over your own knowledge.\n" +
        "- If the knowledgebase does not cover the topic, you may use your own knowledge but state clearly that the answer is not from the knowledgebase.\n\n" +
        `<knowledgebase>\n${flatText}\n</knowledgebase>`;
    }

    // Search mode uses Perplexity which has built-in web search
    if (args.mode === "search") {
      systemPrompt =
        "You are a helpful assistant with web search access. " +
        "Answer clearly and concisely. Cite your sources with URLs when using search results.";
    }

    const apiKey = process.env.AI_GATEWAY_API_KEY;
    if (!apiKey) throw new Error("AI_GATEWAY_API_KEY not set");

    const model = args.mode === "search" ? "perplexity/sonar" : args.model;

    const body = {
      model,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: `<user_query>\n${args.prompt}\n</user_query>` },
      ],
    };

    const resp = await fetch("https://ai-gateway.vercel.sh/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`AI Gateway error (${resp.status}): ${text}`);
    }

    const data = (await resp.json()) as {
      choices: { message: { content: string } }[];
    };
    return data.choices[0].message.content;
  },
});
