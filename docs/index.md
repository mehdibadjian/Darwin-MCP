# Darwin-MCP Documentation

Complete guide to understanding, deploying, and extending the mcp-evolution-core Brain.

## Quick Start

**New to Darwin-MCP?** Start here:

1. **[README](../README.md)** — What is Darwin-MCP? Architecture overview and quick start.
2. **[Getting Started Tutorial](tutorials/getting-started.md)** — Step-by-step local setup, first skill creation, and testing.
3. **[How-To Guides](how-to/common-tasks.md)** — Practical recipes for common tasks (deploy, debug, optimize).

## Documentation Sections

### 📚 Tutorials

Learn by doing. Follow guided walkthroughs.

- **[Getting Started](tutorials/getting-started.md)** — Local setup, create your first skill, verify installation (15 min)

### 📖 How-To Guides

Recipes for specific tasks. Find what you need quickly.

- **[Common Tasks](how-to/common-tasks.md)**
  - Create a skill with external dependencies
  - Debug a failed mutation
  - Test locally before submission
  - Deploy to production
  - Monitor Brain health
  - Rollback a skill version
  - Handle merge conflicts
  - Troubleshoot resource limits
- **[Meshnet Setup](how-to/meshnet-setup.md)** — Connect Gemma 2b on your phone to Darwin-MCP over NordVPN Meshnet

### 📋 Reference

Deep technical documentation. Contracts, schemas, architecture.

- **[Technical Manifesto](reference/technical-manifesto.md)** — Complete API contracts, Git state machine, sandbox isolation, BSL biosafety layers
- **[Agile Backlog](reference/agile-backlog.md)** — Epics, user stories, acceptance criteria, sprint plans
- **[Cloud-less AI Plan](reference/cloudless-ai-plan.md)** — Gemma 2b × Darwin-MCP architecture, tool routing, self-healing wrapper, Meshnet handover

---

## Navigation by Role

### 📡 I want to run Gemma 2b on my phone with Darwin
→ [Cloud-less AI Plan](reference/cloudless-ai-plan.md) + [How-To: Meshnet Setup](how-to/meshnet-setup.md)

### 🚀 I want to get started quickly
→ [Getting Started Tutorial](tutorials/getting-started.md)

### 🛠️ I need to do something specific
→ [How-To: Common Tasks](how-to/common-tasks.md)

### 🏗️ I want to understand the architecture
→ [Technical Manifesto](reference/technical-manifesto.md)

### 📊 I'm planning sprints or features
→ [Agile Backlog](reference/agile-backlog.md)

### 💬 I need help with my skill
→ [How-To: Debugging](how-to/common-tasks.md#debug-a-failed-mutation)

---

## Key Concepts at a Glance

| Concept | Explanation | Link |
|---------|-------------|------|
| **Species** | A registered AI skill — a Python module | [Manifesto](reference/technical-manifesto.md) |
| **Mutation** | Submitting code + tests for evolution | [Getting Started](tutorials/getting-started.md#step-8-create-your-first-skill) |
| **Registry** | `memory/dna/registry.json` — index of all skills | [How-To: View Registry](how-to/common-tasks.md#view-skill-metadata-in-the-registry) |
| **Sandbox** | Isolated virtualenv for safe testing | [Manifesto](reference/technical-manifesto.md#isolation) |
| **Circuit Breaker** | Safety limits (recursion, CPU, memory) | [How-To: Troubleshoot](how-to/common-tasks.md#troubleshoot-resource-limits) |
| **Brain** | The stateless SSE server | [Manifesto](reference/technical-manifesto.md) |
| **Memory** | Git submodule storing species and registry | [Getting Started](tutorials/getting-started.md#step-2-initialize-the-memory-submodule) |

---

## Common Issues & Solutions

**Skills won't register?** → [Debug Failed Mutation](how-to/common-tasks.md#debug-a-failed-mutation)

**Getting 401 Unauthorized?** → [Getting Started: Troubleshooting](tutorials/getting-started.md#troubleshooting)

**Tests fail locally but pass on Brain?** → [Test Before Submission](how-to/common-tasks.md#test-skills-locally-before-submission)

**Need to rollback?** → [Rollback a Skill](how-to/common-tasks.md#rollback-a-skill-to-a-previous-version)

**Deploying to production?** → [Deploy to Droplet](how-to/common-tasks.md#deploy-the-brain-to-production)

---

## Repository Structure

```
docs/
├── index.md                    ← You are here
├── tutorials/
│   └── getting-started.md      ← Setup, create first skill
├── how-to/
│   ├── common-tasks.md         ← Practical recipes
│   └── meshnet-setup.md        ← Gemma 2b + NordVPN Meshnet
└── reference/
    ├── technical-manifesto.md  ← API contracts
    ├── agile-backlog.md        ← Sprint planning
    └── cloudless-ai-plan.md    ← Gemma 2b × Darwin-MCP architecture
```

---

## Additional Resources

- **[Main README](../README.md)** — What is Darwin-MCP? Quick start.
- **[GitHub Issues](https://github.com/yourusername/mcp-evolution-core/issues)** — Bug reports and feature requests.
- **[Discussions](https://github.com/yourusername/mcp-evolution-core/discussions)** — Q&A and community.

---

**Ready to train your Brain?** [Start here →](tutorials/getting-started.md)
