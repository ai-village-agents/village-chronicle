# Automated Event Log Sync

This repository includes an automated CI/CD solution to keep the `village-chronicle` events.json synchronized with the source `village-event-log` repository.

## Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ village-event-log   │────│  GitHub Actions     │────│ village-chronicle   │
│ (source of truth)   │    │  Sync Workflow      │    │ (visualization)     │
│                     │    │                     │    │                     │
│ - events.json       │    │ - Daily cron @ 9UTC │    │ - events.json       │
│ - Validator scripts │    │ - On push to main   │    │ - Timeline HTML/JS  │
│ - Guardrails        │    │ - Manual trigger    │    │ - Stats dashboard   │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

## Components

### 1. `sync_events.py` Script
Main sync script that:
- Clones/updates the `village-event-log` repository
- Runs the unified validator on `events.json`
- Validates email privacy guardrails
- Updates metadata with sync timestamps
- Detects changes and writes updates

### 2. GitHub Actions Workflow (`.github/workflows/sync-events.yml`)
- **Schedule**: Daily at 09:00 UTC (2:00 AM PT)
- **Triggers**: Push to main, manual workflow dispatch
- **Validation**: Runs before any changes are committed
- **Auto-commit**: Only if changes detected

### 3. Validation Guardrails
1. **Structural validation**: JSON schema, required fields
2. **Email privacy**: Only @agentvillage.org emails allowed
3. **Metadata consistency**: `total_events` matches actual count
4. **Date formula verification**: Dates match canonical Day N formula
5. **Intra-day consistency**: All events on same day share same date

## Usage

### Manual Sync
```bash
python3 sync_events.py
```

### GitHub Actions
- **Automatic**: Runs daily at 09:00 UTC
- **Manual**: Go to Actions → "Sync Event Log" → Run workflow
- **Push-triggered**: Any push to main branch

### Workflow Inputs (Manual Trigger)
- `force_sync`: Force sync even if no changes detected (default: false)

## Data Flow

1. Clone `village-event-log` repo (temp directory)
2. Run `scripts/validate_events.py` on source `events.json`
3. If validation passes, compare with current `events.json`
4. If changes detected:
   - Update metadata with sync timestamp
   - Fix known issues (e.g., "465 events" → "466 events" typo)
   - Commit with descriptive message
   - Push to main branch

## Error Handling

- **Validation fails**: No changes committed, workflow fails
- **Git conflicts**: Manual intervention required
- **Network issues**: Retry logic in script
- **Schema changes**: Manual review needed if event structure changes

## Configuration

### Environment Variables
- `GITHUB_TOKEN`: Automatically provided by GitHub Actions
- No additional secrets required (public repos)

### Cron Schedule
- `0 9 * * *` = Daily at 09:00 UTC
- Adjust in `.github/workflows/sync-events.yml` if needed

## Monitoring

Check GitHub Actions page for:
- Last sync status
- Number of events synced
- Validation results
- Change detection logs

## Maintenance

### Adding New Validation Rules
1. Update `scripts/validate_events.py` in `village-event-log`
2. The sync script will automatically use updated validator
3. Test with manual sync before relying on automation

### Schema Changes
If the event schema changes significantly:
1. Update sync script to handle new fields
2. Test locally first
3. Consider backward compatibility

## Troubleshooting

### Sync Not Running
- Check GitHub Actions permissions
- Verify cron syntax (uses UTC)
- Check repository secrets

### Validation Errors
- Run validator locally: `python3 scripts/validate_events.py`
- Check for email privacy violations
- Verify metadata consistency

### No Changes Detected When Expected
- Check if source and destination have same content
- Run with `force_sync: true` in manual trigger
- Verify git diff output

## Dependencies

- Python 3.11+
- Git
- GitHub Actions environment
- Access to public GitHub repos (no authentication needed)

## Related Documentation

- [Event Log Guardrails](https://github.com/ai-village-agents/village-event-log/blob/main/docs/event-log-guardrails.md)
- [Email Privacy Policy](https://github.com/ai-village-agents/village-event-log/blob/main/docs/email-privacy-policy.md)
- [Chronicle Documentation](https://github.com/ai-village-agents/village-chronicle/blob/main/README.md)

## Contact

For issues with the sync system, open an issue in the `village-chronicle` repository or contact the AI Village agents via chat.
