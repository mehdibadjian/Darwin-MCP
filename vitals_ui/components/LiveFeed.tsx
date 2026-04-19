"use client";

import { useEffect, useRef, useState } from "react";

export default function LiveFeed() {
  const [lines, setLines] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const es = new EventSource("/api/feed");
    es.onmessage = (e) => {
      try {
        const line: string = JSON.parse(e.data);
        setLines((prev) => [...prev.slice(-200), line]);
      } catch { /* ignore malformed */ }
    };
    return () => es.close();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <section className="bg-sovereign-panel border border-sovereign-border rounded p-4">
      <h2 className="text-sovereign-accent text-sm font-bold uppercase tracking-widest mb-3">
        ▸ Metabolism Record — progress.txt
      </h2>
      <div className="h-64 overflow-y-auto text-xs leading-relaxed space-y-0.5">
        {lines.length === 0 ? (
          <p className="text-sovereign-muted italic">Awaiting signal…</p>
        ) : (
          lines.map((l, i) => (
            <p key={i} className="font-mono text-sovereign-text hover:text-sovereign-accent transition-colors">
              {l}
            </p>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </section>
  );
}
