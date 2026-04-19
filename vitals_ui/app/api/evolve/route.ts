import { NextRequest, NextResponse } from "next/server";

const BRAIN_URL = process.env.NEXT_PUBLIC_BRAIN_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await fetch(`${BRAIN_URL}/evolve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${process.env.MCP_BEARER_TOKEN ?? ""}`,
      },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
