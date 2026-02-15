import { v } from "convex/values";
import type { Id } from "./_generated/dataModel";
import { query, action, internalMutation } from "./_generated/server";
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
      }),
    });
    if (!resp.ok) {
      throw new Error(`tunnel request failed (${resp.status})`);
    }
    return sessionId;
  },
});

// --- Queries ---

export const listSessions = query({
  handler: async (ctx) => {
    return await ctx.db
      .query("sessions")
      .order("desc")
      .collect();
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
