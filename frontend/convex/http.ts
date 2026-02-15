import { httpRouter } from "convex/server";
import { httpAction } from "./_generated/server";
import { internal } from "./_generated/api";

function checkSecret(secret: string | undefined): boolean {
  return !!secret && secret === process.env.BEEWORK_SECRET_KEY;
}

const http = httpRouter();

http.route({
  path: "/ingest",
  method: "POST",
  handler: httpAction(async (ctx, req) => {
    const body = await req.json();
    if (!checkSecret(body.secret)) {
      return new Response("unauthorized", { status: 401 });
    }
    if (body.kind === "log") {
      await ctx.runMutation(internal.sessions.appendLogs, {
        sessionId: body.sessionId,
        text: body.text,
      });
    } else if (body.kind === "event") {
      await ctx.runMutation(internal.sessions.addEvent, {
        sessionId: body.sessionId,
        type: body.type,
        data: body.data ?? {},
      });
    }
    return Response.json({ ok: true });
  }),
});

http.route({
  path: "/updateStatus",
  method: "POST",
  handler: httpAction(async (ctx, req) => {
    const body = await req.json();
    if (!checkSecret(body.secret)) {
      return new Response("unauthorized", { status: 401 });
    }
    await ctx.runMutation(internal.sessions.updateSessionStatus, {
      sessionId: body.sessionId,
      status: body.status,
    });
    return Response.json({ ok: true });
  }),
});

export default http;
