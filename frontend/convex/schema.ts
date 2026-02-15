import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  sessions: defineTable({
    repo: v.string(),
    status: v.string(), // "pending" | "running" | "completed" | "failed"
    researchWorkers: v.number(),
    reviewWorkers: v.number(),
    createdAt: v.number(),
  }),

  logs: defineTable({
    sessionId: v.id("sessions"),
    text: v.string(),
    createdAt: v.number(),
  }).index("by_session", ["sessionId", "createdAt"]),

  events: defineTable({
    sessionId: v.id("sessions"),
    type: v.string(),
    data: v.any(),
    createdAt: v.number(),
  }).index("by_session", ["sessionId", "createdAt"]),
});
