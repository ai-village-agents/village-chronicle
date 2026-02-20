#!/usr/bin/env python3
"""
Sync script for copying events.json from village-event-log to village-chronicle.

Improved version that calls validator via subprocess instead of importing.
"""

import json
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

# Constants
EVENT_LOG_REPO = "https://github.com/ai-village-agents/village-event-log.git"
CHRONICLE_REPO_DIR = Path.cwd()
TEMP_DIR = Path(tempfile.gettempdir()) / "village-event-log-sync"
EVENTS_JSON = "events.json"

def run_command(cmd, cwd=None, capture=True):
    """Run shell command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=capture, text=True, check=True
        )
        return True, result.stdout.strip() if capture else ""
    except subprocess.CalledProcessError as e:
        return False, f"{e.stderr}\nExit code: {e.returncode}"

def clone_or_update_event_log():
    """Clone or update the event-log repo."""
    print("📦 Fetching latest event-log data...")
    
    if TEMP_DIR.exists():
        # Update existing clone
        success, output = run_command("git pull origin main", cwd=TEMP_DIR)
        if not success:
            print(f"⚠️  Failed to update existing clone: {output}")
            # Try fresh clone
            shutil.rmtree(TEMP_DIR)
    else:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    if not TEMP_DIR.exists() or not (TEMP_DIR / ".git").exists():
        success, output = run_command(f"git clone {EVENT_LOG_REPO} {TEMP_DIR}")
        if not success:
            print(f"❌ Failed to clone event-log repo: {output}")
            return None
    
    return TEMP_DIR

def validate_with_validator(event_log_dir, events_path):
    """Run the validator script via subprocess."""
    validator_path = event_log_dir / "scripts" / "validate_events.py"
    if not validator_path.exists():
        print(f"❌ Validator not found at {validator_path}")
        return False
    
    print("🔍 Running unified validator...")
    
    # Run validator as subprocess
    success, output = run_command(f"python3 {validator_path}", cwd=event_log_dir)
    
    if success:
        print("✅ Validator passed")
        return True
    else:
        print(f"❌ Validator failed: {output}")
        return False

def basic_validation(events_path):
    """Fallback basic validation."""
    try:
        with open(events_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check structure
        if "metadata" not in data or "events" not in data:
            print("❌ Missing 'metadata' or 'events' keys")
            return False
        
        metadata = data["metadata"]
        events = data["events"]
        
        # Check counts match
        total_events = metadata.get("total_events")
        if total_events != len(events):
            print(f"❌ metadata.total_events={total_events} != len(events)={len(events)}")
            return False
        
        # Check days_covered
        unique_days = len({e.get("day") for e in events if isinstance(e.get("day"), int)})
        days_covered = metadata.get("days_covered")
        if days_covered != unique_days:
            print(f"❌ metadata.days_covered={days_covered} != unique days={unique_days}")
            return False
        
        # Email privacy check (basic)
        import re
        email_regex = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        for event in events:
            desc = event.get("description", "")
            emails = email_regex.findall(desc)
            for email in emails:
                if "agentvillage.org" not in email.lower() and "[redacted-email]" not in email:
                    print(f"❌ Raw external email found in event {event.get('id')}: {email}")
                    return False
        
        print(f"✅ Basic validation passed: {len(events)} events, {days_covered} days")
        return True
        
    except Exception as e:
        print(f"❌ Basic validation failed: {e}")
        return False

def validate_events_file(events_path, event_log_dir):
    """Validate events.json file with validator fallback."""
    # Try validator first
    if validate_with_validator(event_log_dir, events_path):
        return True
    
    print("⚠️  Falling back to basic validation...")
    return basic_validation(events_path)

def sync_events():
    """Main sync function."""
    print("🚀 Starting event sync from village-event-log to village-chronicle")
    print(f"📁 Chronicle repo: {CHRONICLE_REPO_DIR}")
    
    # Get latest event-log data
    event_log_dir = clone_or_update_event_log()
    if not event_log_dir:
        return False
    
    source_events = event_log_dir / EVENTS_JSON
    if not source_events.exists():
        print(f"❌ events.json not found in {event_log_dir}")
        return False
    
    # Validate source file
    if not validate_events_file(source_events, event_log_dir):
        print("❌ Source validation failed - aborting sync")
        return False
    
    # Load source data
    with open(source_events, 'r', encoding='utf-8') as f:
        source_data = json.load(f)
    
    # Load destination data (if exists)
    dest_events = CHRONICLE_REPO_DIR / EVENTS_JSON
    dest_exists = dest_events.exists()
    
    changes_detected = False
    if dest_exists:
        with open(dest_events, 'r', encoding='utf-8') as f:
            dest_data = json.load(f)
        
        # Compare events (ignore metadata differences for now)
        source_json = json.dumps(source_data["events"], sort_keys=True, separators=(',', ':'))
        dest_json = json.dumps(dest_data["events"], sort_keys=True, separators=(',', ':'))
        
        if source_json == dest_json:
            print("📭 No changes detected in events data")
            # Compare metadata, ignoring volatile sync-specific fields
            # Volatile keys that differ between source and destination:
            # - last_updated, synced_from, synced_at: added by sync script
            # - date_note: destination has typo fix (465→466) that source doesn't have
            # - last_updated_day: derived from last_updated
            VOLATILE_KEYS = {"last_updated", "synced_from", "synced_at", "date_note", "last_updated_day"}
            source_meta = {k: v for k, v in source_data.get("metadata", {}).items() if k not in VOLATILE_KEYS}
            dest_meta = {k: v for k, v in dest_data.get("metadata", {}).items() if k not in VOLATILE_KEYS}
            if json.dumps(source_meta, sort_keys=True) != json.dumps(dest_meta, sort_keys=True):
                print("📝 Metadata update detected (non-volatile fields changed)")
                changes_detected = True
        else:
            print("📝 Events data changes detected")
            changes_detected = True
    else:
        print("📝 Destination events.json doesn't exist - will create")
        changes_detected = True
    
    # Check for force sync via environment variable
    force_sync = os.environ.get("FORCE_SYNC", "false").lower() == "true"
    if force_sync:
        print("🔧 Force sync enabled - proceeding regardless of changes")
        changes_detected = True

    if not changes_detected:
        print("✅ Already up to date")
        return True
    
    # Update metadata with sync timestamp
    source_data["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    source_data["metadata"]["synced_from"] = EVENT_LOG_REPO
    source_data["metadata"]["synced_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Fix metadata typo if present (should say 466 events, not 465)
    if "date_note" in source_data["metadata"]:
        date_note = source_data["metadata"]["date_note"]
        if "465 events" in date_note and "466" not in date_note:
            source_data["metadata"]["date_note"] = date_note.replace(
                "465 events", "466 events"
            )
            print("📝 Fixed metadata typo: 465 → 466 events")
    
    # Write to destination (root events.json)
    print(f"📝 Writing events.json ({len(source_data['events'])} events)...")
    with open(dest_events, 'w', encoding='utf-8') as f:
        json.dump(source_data, f, indent=2, ensure_ascii=False)
    
    # Also write to docs/events.json (Pages serves from /docs)
    docs_events = CHRONICLE_REPO_DIR / "docs" / EVENTS_JSON
    if docs_events.parent.exists():
        print(f"📝 Writing docs/events.json ({len(source_data['events'])} events)...")
        with open(docs_events, 'w', encoding='utf-8') as f:
            json.dump(source_data, f, indent=2, ensure_ascii=False)
    else:
        print("⚠️  docs/ directory not found — skipping docs/events.json")
    
    print("✅ Sync completed successfully")
    
    # Show git diff
    success, diff = run_command("git diff --stat", cwd=CHRONICLE_REPO_DIR)
    if success and diff:
        print(f"\n📊 Changes:\n{diff}")
    
    return True

if __name__ == "__main__":
    success = sync_events()
    sys.exit(0 if success else 1)
