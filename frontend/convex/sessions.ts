import { v } from "convex/values";
import type { Id } from "./_generated/dataModel";
import { query, action, internalMutation, internalQuery } from "./_generated/server";
import { internal } from "./_generated/api";

// --- Mutations ---

export const createSession = internalMutation({
  args: {
    repo: v.string(),
    researchWorkers: v.number(),
    reviewWorkers: v.number(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("sessions", {
      ...args,
      status: "pending",
      createdAt: Date.now(),
    });
  },
});

export const appendLogs = internalMutation({
  args: {
    sessionId: v.id("sessions"),
    text: v.string(),
  },
  handler: async (ctx, args) => {
    await ctx.db.insert("logs", {
      sessionId: args.sessionId,
      text: args.text,
      createdAt: Date.now(),
    });
  },
});

export const addEvent = internalMutation({
  args: {
    sessionId: v.id("sessions"),
    type: v.string(),
    data: v.any(),
  },
  handler: async (ctx, args) => {
    await ctx.db.insert("events", {
      sessionId: args.sessionId,
      type: args.type,
      data: args.data,
      createdAt: Date.now(),
    });
  },
});

export const updateSessionStatus = internalMutation({
  args: {
    sessionId: v.id("sessions"),
    status: v.string(),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.sessionId, { status: args.status });
  },
});

// --- Actions ---

export const startSession = action({
  args: {
    repo: v.string(),
    researchWorkers: v.number(),
    reviewWorkers: v.number(),
    project: v.string(),
    secret: v.string(),
  },
  returns: v.id("sessions"),
  handler: async (ctx, args) => {
    if (args.secret !== process.env.BEEWORK_SECRET_KEY) {
      throw new Error("unauthorized");
    }
    const sessionId: Id<"sessions"> = await ctx.runMutation(
      internal.sessions.createSession,
      {
        repo: args.repo,
        researchWorkers: args.researchWorkers,
        reviewWorkers: args.reviewWorkers,
      },
    );
    const tunnelUrl = process.env.TUNNEL_URL ?? "https://api.beework.cc";
    const resp = await fetch(`${tunnelUrl}/start`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": process.env.BEEWORK_SECRET_KEY!,
      },
      body: JSON.stringify({
        sessionId,
        repo: args.repo,
        researchWorkers: args.researchWorkers,
        reviewWorkers: args.reviewWorkers,
        project: args.project,
        convexSiteUrl: process.env.CONVEX_SITE_URL,
      }),
    });
    if (!resp.ok) {
      throw new Error(`tunnel request failed (${resp.status})`);
    }
    return sessionId;
  },
});

export const fetchRepoTree = action({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    const session = await ctx.runQuery(internal.sessions._getSession, { sessionId: args.sessionId });
    if (!session) return;

    const owner = process.env.GITHUB_OWNER ?? "workerbee-gbt";
    const fullRepo = session.repo.includes("/") ? session.repo : `${owner}/${session.repo}`;

    const pat = process.env.GITHUB_PAT;
    if (!pat) return;

    async function save(tree: { path: string; type: string }[]) {
      await ctx.runMutation(internal.sessions._upsertRepoTree, {
        sessionId: args.sessionId,
        repo: fullRepo,
        tree,
      });
    }

    const headers = { Authorization: `Bearer ${pat}`, Accept: "application/vnd.github+json" };

    const repoResp = await fetch(`https://api.github.com/repos/${fullRepo}`, { headers });
    if (!repoResp.ok) return await save([]);
    const { default_branch } = await repoResp.json() as { default_branch: string };

    const resp = await fetch(
      `https://api.github.com/repos/${fullRepo}/git/trees/${default_branch}?recursive=1`,
      { headers },
    );
    if (!resp.ok) return await save([]);

    const body = await resp.json() as { tree: { path: string; type: string }[] };
    const tree = body.tree.map((e: { path: string; type: string }) => ({ path: e.path, type: e.type }));
    await save(tree);
  },
});

// --- Internal helpers for fetchRepoTree ---

export const _getSession = internalQuery({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.sessionId);
  },
});

export const _upsertRepoTree = internalMutation({
  args: {
    sessionId: v.id("sessions"),
    repo: v.string(),
    tree: v.array(v.object({ path: v.string(), type: v.string() })),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("repoTrees")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .first();
    if (existing) {
      await ctx.db.patch(existing._id, { tree: args.tree, fetchedAt: Date.now() });
    } else {
      await ctx.db.insert("repoTrees", {
        sessionId: args.sessionId,
        repo: args.repo,
        tree: args.tree,
        fetchedAt: Date.now(),
      });
    }
  },
});

// --- Queries ---

export const getSession = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.sessionId);
  },
});

export const listSessions = query({
  handler: async (ctx) => {
    const all = await ctx.db
      .query("sessions")
      .order("desc")
      .collect();
    return all.filter((s) => !s.hidden);
  },
});

export const getSessionLogs = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("logs")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .order("asc")
      .collect();
  },
});

export const getSessionEvents = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("events")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .order("asc")
      .collect();
  },
});

export const getRepoTree = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("repoTrees")
      .withIndex("by_session", (q) => q.eq("sessionId", args.sessionId))
      .first();
  },
});
