"use client";

import { useState } from "react";

export default function ManualOverride() {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [tests, setTests] = useState("");
  const [requirements, setRequirements] = useState("");
  const [status, setStatus] = useState<{
    type: "idle" | "loading" | "ok" | "error";
    message?: string;
  }>({ type: "idle" });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus({ type: "loading" });
    try {
      const res = await fetch("/api/evolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          code,
          tests,
          requirements: requirements
            .split("\n")
            .map((r) => r.trim())
            .filter(Boolean),
        }),
      });
      const data = await res.json();
      if (res.ok && data.status === "success") {
        setStatus({ type: "ok", message: `✅ ${data.message}` });
      } else {
        setStatus({ type: "error", message: `⚠ ${data.message ?? data.error}` });
      }
    } catch (err: any) {
      setStatus({ type: "error", message: `⚠ ${err.message}` });
    }
  };

  const inputCls =
    "w-full bg-sovereign-bg border border-sovereign-border rounded px-3 py-2 text-sm font-mono text-sovereign-text focus:outline-none focus:border-sovereign-accent";

  return (
    <section className="bg-sovereign-panel border border-sovereign-border rounded p-4">
      <h2 className="text-sovereign-accent text-sm font-bold uppercase tracking-widest mb-3">
        ⚡ Manual Override — request_evolution
      </h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          className={inputCls}
          placeholder="skill_name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <textarea
          className={`${inputCls} h-28 resize-y`}
          placeholder="# Python code…"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          required
        />
        <textarea
          className={`${inputCls} h-20 resize-y`}
          placeholder="# pytest tests…"
          value={tests}
          onChange={(e) => setTests(e.target.value)}
          required
        />
        <textarea
          className={`${inputCls} h-12 resize-y`}
          placeholder="requirements (one per line)"
          value={requirements}
          onChange={(e) => setRequirements(e.target.value)}
        />
        <button
          type="submit"
          disabled={status.type === "loading"}
          className="w-full py-2 bg-sovereign-accent text-sovereign-bg font-bold text-sm rounded hover:opacity-90 disabled:opacity-50 transition-opacity uppercase tracking-widest font-mono"
        >
          {status.type === "loading" ? "Evolving…" : "▸ Trigger Evolution"}
        </button>
        {status.message && (
          <p
            className={`text-xs font-mono ${
              status.type === "ok" ? "text-sovereign-accent" : "text-red-400"
            }`}
          >
            {status.message}
          </p>
        )}
      </form>
    </section>
  );
}
