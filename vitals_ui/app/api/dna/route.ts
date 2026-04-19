import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const BRAIN_ROOT = "/Users/pappi/Desktop/dev/mcp-evolution-core";
const REGISTRY_PATH = path.join(BRAIN_ROOT, "memory", "dna", "registry.json");

export async function GET() {
  try {
    const raw = fs.readFileSync(REGISTRY_PATH, "utf-8");
    const registry = JSON.parse(raw);

    const skills = Object.entries(registry.skills || {}).map(
      ([name, entry]: [string, any]) => {
        const success = entry.success_count ?? 0;
        const failure = entry.failure_count ?? 0;
        const total = success + failure;
        const successRate = total === 0 ? 1.0 : success / total;
        return {
          name,
          status: entry.status ?? "unknown",
          version: entry.version ?? 1,
          evolved_at: entry.evolved_at ?? null,
          last_used_at: entry.last_used_at ?? null,
          total_calls: entry.total_calls ?? 0,
          success_rate: Math.round(successRate * 100),
          dependencies: entry.dependencies ?? [],
          short_description: entry.short_description ?? entry.description ?? "",
        };
      }
    );

    return NextResponse.json({
      organism_version: registry.organism_version,
      last_mutation: registry.last_mutation,
      total_species: skills.length,
      skills,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
