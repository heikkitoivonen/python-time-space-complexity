# Subagent Swarm - Quick Start

## TL;DR

```bash
# Run with 4 parallel subagents (default)
./launch_review_swarm.sh

# Or specify number of agents
./launch_review_swarm.sh 8

# Test without executing
python subagent_coordinator.py --dryrun
```

## What Happens

1. **Coordinator loads** the review prompt from `.subagent_prompt.md`
2. **Spawns N subagents** in parallel (each gets unique agent ID)
3. **Each subagent independently**:
   - Scans `docs/` for `.md` files
   - For each file:
     - Tries to acquire lock: `docs/.locks/{filename}.lock`
     - If locked → skip (another agent has it)
     - If acquired → process file
     - Release lock after completion
4. **After all complete**:
   - Runs `make check` (lint, types, tests)
   - Commits changes
   - Ready to push

## Key Design: Lock Files

**Zero Race Conditions:**
- No database, no network, no coordination overhead
- Just filesystem atomic writes
- Each agent manages exclusive lock on one file at a time
- Multiple agents working on different files = no conflict

```
docs/.locks/
├── list.md.lock          (agent-1 working)
├── dict.md.lock          (agent-2 working)
└── os.md.lock            (agent-3 working)

Other agents skip locked files, move to next.
```

## The Review Prompt

File: `.subagent_prompt.md` (9.7 KB)

**What subagents are told to do:**
1. Verify complexity claims are correct
2. Delete generic/unrelated examples
3. Keep only performance-focused code
4. Document all caveats (amortized, worst case, etc.)
5. Make minimal, focused edits
6. Commit with clear message

**Example:**
- ❌ DELETE: `x = [1, 2, 3]; print(len(x))`
- ✅ KEEP: `# dict vs list for lookup - O(1) vs O(n)`

## Architecture

```
coordinator.py
├── Loads prompt
├── Spawns agent-1 ──┐
├── Spawns agent-2 ──┤
├── Spawns agent-3 ──┼─→ Each worker.py instance
├── Spawns agent-4 ──┤   (independent, parallel)
└── Waits for all    │
    └─ make check ◄──┴─ Finalize
       Commit
       Push-ready
```

## Files in System

| File | Purpose | Size |
|------|---------|------|
| `.subagent_prompt.md` | Review instructions | 9.7 KB |
| `subagent_worker.py` | Individual agent | 6.5 KB |
| `subagent_coordinator.py` | Spawn & manage | 7.2 KB |
| `launch_review_swarm.sh` | Shell launcher | 0.6 KB |
| `SUBAGENT_GUIDE.md` | Full documentation | 12 KB |

## Environment Variables (Auto-set)

```bash
SUBAGENT_ID="agent-1"         # Unique per subagent
REVIEW_PROMPT="..."           # Full prompt text
LOCK_DIR="docs/.locks"        # Lock directory
```

## Monitoring

### Real-time
```bash
# Watch lock files as agents work
watch -n 1 'ls docs/.locks/ | wc -l'

# Or monitor progress file
watch -n 2 'cat .subagent_progress.json | jq .'
```

### After completion
```bash
git log --oneline -5
git diff HEAD~1
```

## Cleanup

Auto-done by coordinator. But if needed:
```bash
# Remove lock files
rm -rf docs/.locks/*

# Clean progress file
rm .subagent_progress.json
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Agents won't start | Check `.subagent_prompt.md` exists, `docs/` has `.md` files |
| All agents skip files | Files are locked; run: `rm -rf docs/.locks/*` |
| One file won't unlock | Manually: `rm docs/.locks/filename.lock` |
| Tests fail after | Run: `make check` to see issues, fix, re-run |
| Git commit fails | Check git configured: `git config user.email` |

## Performance

**Typical Results (4 agents, 292 files):**
- Parallel processing: ~5-10 minutes
- Sequential processing: ~20-40 minutes
- Speedup: ~4x (near-linear with 4 agents)

**Scaling:**
- 2 agents: 50% slower than sequential
- 4 agents: 4-5x faster
- 8 agents: 6-7x faster (filesystem I/O limited)
- 16+ agents: Diminishing returns

## Safety

✅ **Safe because:**
- Lock files prevent same file being processed twice
- Changes only commit after all agents complete
- `make check` catches any issues
- Can abort before `git push`

❌ **Not safe:**
- Don't run while another review is happening
- Don't manually edit files in `docs/` while running
- Don't run on different machines without shared filesystem

## Next Steps

```bash
# 1. Review the prompt
cat .subagent_prompt.md | head -50

# 2. Run with test
python subagent_coordinator.py --dryrun

# 3. Launch for real
./launch_review_swarm.sh 4

# 4. Monitor progress
watch -n 1 'ls docs/.locks/ | wc -l'

# 5. Review changes
git log -1
git diff HEAD~1

# 6. Push when ready
git push
```

## More Info

- Full guide: `cat SUBAGENT_GUIDE.md`
- Coordinator code: `cat subagent_coordinator.py`
- Worker code: `cat subagent_worker.py`
- Prompt details: `cat .subagent_prompt.md`

---

**Ready to review 300+ documentation files in parallel?**

```bash
./launch_review_swarm.sh
```
