import LiveFeed from "@/components/LiveFeed";
import DnaMap from "@/components/DnaMap";
import ManualOverride from "@/components/ManualOverride";

export default function Home() {
  return (
    <main className="max-w-7xl mx-auto p-6 space-y-6">
      <header className="border-b border-sovereign-border pb-4">
        <h1 className="text-2xl font-bold text-sovereign-accent tracking-widest uppercase">
          ◈ Darwin-MCP Intelligence Dashboard
        </h1>
        <p className="text-sovereign-muted text-sm mt-1">
          Organism vitals · DNA registry · Manual evolution trigger
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <LiveFeed />
          <ManualOverride />
        </div>
        <DnaMap />
      </div>
    </main>
  );
}
