#!/usr/bin/env python3
"""
Subagent worker for parallel documentation review.

Usage:
    export REVIEW_PROMPT=$(cat .subagent_prompt.md)
    export AGENT_ID=agent-1
    python subagent_worker.py
"""

import os
from datetime import datetime
from pathlib import Path

AGENT_ID = os.environ.get("SUBAGENT_ID", "unknown")
LOCK_DIR = Path(os.environ.get("LOCK_DIR", "docs/.locks"))
LOCK_DIR.mkdir(parents=True, exist_ok=True)


def acquire_lock(filepath):
    """Try to acquire exclusive lock on file. Returns lock path or None if locked."""
    lock_file = LOCK_DIR / f"{Path(filepath).stem}.lock"

    if lock_file.exists():
        # File is locked by another agent
        return None

    try:
        # Atomic lock creation
        lock_file.write_text(f"{AGENT_ID}\n{datetime.now().isoformat()}\n")
        return lock_file
    except Exception:
        return None


def release_lock(lock_file):
    """Release lock on file."""
    try:
        if lock_file:
            lock_file.unlink()
    except Exception:
        pass


def get_review_summary(filepath):
    """
    Parse file to identify what needs review.
    This is a simple analysis - in real use, Amp would do this.
    """
    content = Path(filepath).read_text()

    summary = {
        "filepath": filepath,
        "has_complexity_table": "| Operation | Time | Space |" in content,
        "has_examples": "```python" in content,
        "has_best_practices": "✅ DO" in content or "❌ DON'T" in content,
        "size": len(content),
    }

    return summary


def process_file(filepath):
    """
    Process one file: acquire lock, analyze, prepare for review, release lock.
    Returns True if successfully queued for review.
    """
    lock = acquire_lock(filepath)
    if not lock:
        # File is locked by another agent, skip
        return False

    try:
        filepath = Path(filepath).resolve()
        rel_path = filepath.relative_to(Path.cwd())
        summary = get_review_summary(filepath)

        print(f"[{AGENT_ID}] Processing: {rel_path}")

        # In real implementation, this would call Amp API with:
        # - File content
        # - Review prompt
        # - Specific instructions for this file type

        # For now, just log what would be reviewed
        if summary["has_complexity_table"]:
            print("  ✓ Has complexity table")
        else:
            print("  ⚠ Missing complexity table")

        if summary["has_examples"]:
            print("  ✓ Has code examples")
        else:
            print("  ⚠ Missing code examples")

        if summary["has_best_practices"]:
            print("  ✓ Has best practices")
        else:
            print("  ⚠ Missing best practices")

        print(f"  Size: {summary['size']} bytes")

        # Mark as processed (in real implementation, would commit changes)
        print(f"[{AGENT_ID}] ✓ {rel_path}")

        return True

    except Exception as e:
        print(f"[{AGENT_ID}] ✗ Error processing {filepath}: {e}")
        return False

    finally:
        release_lock(lock)


def get_md_files():
    """Get all .md files to review, excluding index.md"""
    docs_dir = Path("docs")
    if not docs_dir.exists():
        print(f"[{AGENT_ID}] Error: docs/ directory not found")
        return []

    files = sorted(docs_dir.rglob("*.md"))
    # Exclude index.md files and hidden files
    files = [f for f in files if f.name != "index.md" and not f.name.startswith(".")]

    return files


def main():
    """Main subagent loop"""
    print(f"[{AGENT_ID}] Starting documentation review")
    print(f"[{AGENT_ID}] Lock directory: {LOCK_DIR}")

    md_files = get_md_files()
    print(f"[{AGENT_ID}] Found {len(md_files)} files to review")

    if not md_files:
        print(f"[{AGENT_ID}] No documentation files found")
        return

    processed = 0
    skipped = 0
    failed = 0

    for filepath in md_files:
        try:
            if process_file(str(filepath)):
                processed += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"[{AGENT_ID}] Exception on {filepath}: {e}")
            failed += 1

    print(f"[{AGENT_ID}] Complete:")
    print(f"  Processed: {processed}")
    print(f"  Skipped (locked): {skipped}")
    print(f"  Failed: {failed}")
    print(f"[{AGENT_ID}] Exiting")


if __name__ == "__main__":
    main()
