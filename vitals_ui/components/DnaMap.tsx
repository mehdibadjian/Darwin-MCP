"use client";

import { useEffect, useState } from "react";

interface Species {
  name: string;
  status: string;
  version: number;
  evolved_at: string | null;
  last_used_at: string | null;
  total_calls: number;
  success_rate: number;
  dependencies: string[];
  short_description: string;
}

interface DnaData {
  organism_version: string;
  last_mutation: string | null;
  total_species: number;
  skills: Species[];
}

function SuccessBar({ rate }: { rate: number }) {
  const color =
    rate >= 80 ? "bg-sovereign-accent" : rate >= 50 ? "bg-yellow-500" : "bg-red-600";
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex-1 h-1 bg-sovereign-border rounded">
        <div className={`h-1 rounded ${color}`} style={{ width: `${rate}%` }} />
      </div>
      <span className="text-xs text-sovereign-muted w-10 text-right">{rate}%</span>
    </div>
  );
}

export default function DnaMap() {
  const [data, setData] = useState<DnaData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    fetch("/api/dna")
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(e.message));
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15000);
    return () => clearInterval(id);
  }, []);

  if (error) return <p className="text-red-500 text-xs p-4">{error}</p>;
  if (!data) return <p className="text-sovereign-muted text-xs p-4 italic">Loading DNA Map…</p>;

  return (
    <section className="bg-sovereign-panel border border-sovereign-border rounded p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sovereign-accent text-sm font-bold uppercase tracking-widest">
          🧬 DNA Map — {data.total_species} Species
        </h2>
        <span className="text-sovereign-muted text-xs">v{data.organism_version}</span>
      </div>

      <div className="space-y-3 max-h-[32rem] overflow-y-auto pr-1">
        {data.skills.map((s) => (
          <div
            key={s.name}
            className="border border-sovereign-border rounded p-3 hover:border-sovereign-accent transition-colors"
          >
            <div className="flex items-start justify-between">
              <span className="font-mono font-bold text-sovereign-accent text-sm">{s.name}</span>
              <span
                className={`text-xs px-1.5 py-0.5 rounded font-mono ${
                  s.status === "active"
                    ? "bg-green-900 text-green-400"
                    : s.status === "Toxic"
                    ? "bg-red-900 text-red-400"
                    : "bg-yellow-900 text-yellow-400"
                }`}
              >
                {s.status} v{s.version}
              </span>
            </div>
            {s.short_description && (
              <p className="text-sovereign-muted text-xs mt-1 truncate">{s.short_description}</p>
            )}
            <SuccessBar rate={s.success_rate} />
            <div className="flex flex-wrap gap-4 mt-1 text-sovereign-muted text-xs">
              <span>calls: {s.total_calls}</span>
              {s.evolved_at && (
                <span>evolved: {new Date(s.evolved_at).toLocaleDateString()}</span>
              )}
              {s.dependencies.length > 0 && (
                <span>deps: {s.dependencies.join(", ")}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
