import fs from "fs";
import path from "path";

const BRAIN_ROOT = "/Users/pappi/Desktop/dev/mcp-evolution-core";
const PROGRESS_PATH = path.join(BRAIN_ROOT, "progress.txt");
const POLL_MS = 2000;

export async function GET() {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      let lastSize = 0;

      // Seed with last 20 lines immediately
      try {
        const content = fs.readFileSync(PROGRESS_PATH, "utf-8");
        const lines = content.trim().split("\n").slice(-20);
        for (const line of lines) {
          if (line) controller.enqueue(encoder.encode(`data: ${JSON.stringify(line)}\n\n`));
        }
        lastSize = fs.statSync(PROGRESS_PATH).size;
      } catch { /* file may not exist yet */ }

      function poll() {
        try {
          const stat = fs.statSync(PROGRESS_PATH);
          if (stat.size > lastSize) {
            const len = stat.size - lastSize;
            const buf = Buffer.alloc(len);
            const fd = fs.openSync(PROGRESS_PATH, "r");
            fs.readSync(fd, buf, 0, len, lastSize);
            fs.closeSync(fd);
            lastSize = stat.size;
            for (const line of buf.toString("utf-8").trim().split("\n")) {
              if (line) controller.enqueue(encoder.encode(`data: ${JSON.stringify(line)}\n\n`));
            }
          } else {
            controller.enqueue(encoder.encode(": keepalive\n\n"));
          }
        } catch {
          controller.enqueue(encoder.encode(": keepalive\n\n"));
        }
      }

      const interval = setInterval(poll, POLL_MS);
      return () => clearInterval(interval);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
