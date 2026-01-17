#!/usr/bin/env python3
"""
Coordinator for spawning parallel documentation review subagents.

This script:
1. Loads the review prompt
2. Spawns N subagents
3. Monitors their progress
4. Waits for completion
5. Coordinates final git operations

Usage:
    python subagent_coordinator.py --agents 4

Environment:
    SUBAGENT_ID: Set by coordinator for each agent
    REVIEW_PROMPT: Loaded from .subagent_prompt.md
    LOCK_DIR: docs/.locks
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class SubagentCoordinator:
    def __init__(self, num_agents=4, dryrun=False):
        self.num_agents = num_agents
        self.dryrun = dryrun
        self.prompt = self.load_prompt()
        self.lock_dir = Path("docs/.locks")
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = Path(".subagent_progress.json")

    def load_prompt(self):
        """Load review prompt from .subagent_prompt.md"""
        prompt_file = Path(".subagent_prompt.md")

        if not prompt_file.exists():
            print("ERROR: .subagent_prompt.md not found")
            print("Create it with: cp subagent_prompt_template.md .subagent_prompt.md")
            sys.exit(1)

        content = prompt_file.read_text()
        print(f"✓ Loaded prompt ({len(content)} bytes)")
        return content

    def init_progress(self):
        """Initialize progress tracking"""
        md_files = sorted(Path("docs").rglob("*.md"))
        md_files = [
            str(f)
            for f in md_files
            if f.name != "index.md" and not f.name.startswith(".")
        ]

        progress = {
            "started": datetime.now().isoformat(),
            "total_files": len(md_files),
            "completed": [],
            "in_progress": [],
            "failed": [],
        }

        self.progress_file.write_text(json.dumps(progress, indent=2))
        print(f"✓ Initialized progress tracking ({len(md_files)} files)")

    def get_progress(self):
        """Get current progress"""
        if not self.progress_file.exists():
            return None

        return json.loads(self.progress_file.read_text())

    def spawn_subagents(self):
        """Spawn N subagent processes in parallel"""
        self.init_progress()

        processes = []
        print(f"\n{'=' * 60}")
        print(f"Spawning {self.num_agents} subagents")
        print(f"{'=' * 60}\n")

        env = os.environ.copy()
        env["REVIEW_PROMPT"] = self.prompt
        env["LOCK_DIR"] = str(self.lock_dir)

        for i in range(1, self.num_agents + 1):
            agent_id = f"agent-{i}"
            env["SUBAGENT_ID"] = agent_id

            if self.dryrun:
                print(f"[DRY-RUN] Would spawn: {agent_id}")
                continue

            try:
                proc = subprocess.Popen(
                    [sys.executable, "subagent_worker.py"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                processes.append((agent_id, proc))
                print(f"✓ Spawned {agent_id} (PID: {proc.pid})")
            except Exception as e:
                print(f"✗ Failed to spawn {agent_id}: {e}")

        if self.dryrun:
            print("\n[DRY-RUN] Would wait for agents to complete")
            return

        print(f"\n{'=' * 60}")
        print("Waiting for subagents to complete...")
        print(f"{'=' * 60}\n")

        # Wait for all agents to complete
        for agent_id, proc in processes:
            try:
                stdout, _ = proc.communicate(timeout=3600)  # 1 hour timeout
                if proc.returncode == 0:
                    print(f"✓ {agent_id} completed successfully")
                else:
                    print(f"✗ {agent_id} exited with code {proc.returncode}")
                    if stdout:
                        print(f"  Output: {stdout[:200]}")
            except subprocess.TimeoutExpired:
                print(f"✗ {agent_id} timeout (>1 hour)")
                proc.kill()
            except Exception as e:
                print(f"✗ {agent_id} error: {e}")

        print(f"\n{'=' * 60}")
        print("All subagents completed")
        print(f"{'=' * 60}\n")

    def show_progress(self):
        """Show current progress"""
        progress = self.get_progress()
        if not progress:
            return

        total = progress["total_files"]
        completed = len(progress["completed"])
        in_progress = len(progress["in_progress"])
        failed = len(progress["failed"])
        pending = total - completed - in_progress - failed

        print("\nProgress Report:")
        print(f"  Total files: {total}")
        print(f"  Completed:   {completed} ({100*completed/total:.1f}%)")
        print(f"  In progress: {in_progress}")
        print(f"  Failed:      {failed}")
        print(f"  Pending:     {pending}")

    def cleanup_locks(self):
        """Clean up any remaining lock files"""
        locks = list(self.lock_dir.glob("*.lock"))
        if locks:
            print(f"\nCleaning up {len(locks)} stale lock files...")
            for lock in locks:
                lock.unlink()
                print(f"  Removed: {lock.name}")

    def finalize(self):
        """Run post-review operations"""
        if self.dryrun:
            print("\n[DRY-RUN] Would run final operations")
            return

        print(f"\n{'=' * 60}")
        print("Finalizing documentation review")
        print(f"{'=' * 60}\n")

        # Run quality checks
        print("Running quality checks...")
        result = subprocess.run(["make", "check"], cwd=Path.cwd())

        if result.returncode == 0:
            print("\n✓ All quality checks passed")

            # Stage changes
            print("\nStaging changes...")
            subprocess.run(["git", "add", "docs/"])

            # Create summary commit
            print("Creating summary commit...")
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    "Review: Documentation complexity analysis complete\n\nParallel review by subagents complete.\nAll documentation files reviewed for complexity accuracy.\n\nCo-Authored-By: Subagent Swarm",
                ]
            )

            print("\n✓ Changes committed")
            print("\nNext steps:")
            print("  1. Review changes: git log --oneline -5")
            print("  2. Push: git push")
        else:
            print("\n✗ Quality checks failed. Review required before push.")
            print("  Run: make check")

        self.show_progress()

    def run(self):
        """Run the coordinator"""
        print(f"\n{'=' * 60}")
        print("Subagent Documentation Review Coordinator")
        print(f"{'=' * 60}\n")

        print("Configuration:")
        print(f"  Agents: {self.num_agents}")
        print("  Prompt file: .subagent_prompt.md")
        print(f"  Lock directory: {self.lock_dir}")
        print(f"  Dry run: {self.dryrun}")

        # Main workflow
        self.spawn_subagents()
        self.cleanup_locks()
        self.show_progress()
        self.finalize()

        print(f"\n{'=' * 60}")
        print("✓ Documentation review coordinator complete")
        print(f"{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Coordinate parallel documentation review subagents"
    )
    parser.add_argument(
        "--agents",
        type=int,
        default=4,
        help="Number of parallel subagents to spawn (default: 4)",
    )
    parser.add_argument(
        "--dryrun",
        action="store_true",
        help="Dry run - show what would happen without executing",
    )

    args = parser.parse_args()

    coordinator = SubagentCoordinator(num_agents=args.agents, dryrun=args.dryrun)
    coordinator.run()


if __name__ == "__main__":
    main()
