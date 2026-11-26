# Screenshots

These are real captures of a running Seclyst instance. Nothing here is a mockup
or a design render.

| File | Shows |
| --- | --- |
| `home.png` | The command center: tool status, recent activity, and platform summary |
| `activity.png` | The unified activity timeline across all five tools |
| `login.png` | The access gate on first run |
| `tool-ioc.png` | IOC Lookup: multi-provider enrichment and consensus verdict |
| `tool-malware.png` | Malware Analyzer: payload analysis and indicator reporting |
| `tool-phishing.png` | Phishing Detector: mail forensics and sender authentication |
| `tool-events.png` | Event Analyzer: EVTX search and Sigma hunting |
| `tool-ruleforge.png` | RuleForge: detection rule authoring and translation |

## Regenerating

The five `tool-*.png` images are produced from a live build, not hand-picked:

```bash
python scripts/capture_tool_overviews.py
```

The script starts the supervisor with all five engines on scratch ports
(7200-7205), opens each tool in headless Chrome at 1440x1000, and writes the
frames into this directory. It requires `selenium` (in `requirements-dev.txt`)
and a Chrome installation.

`home.png`, `activity.png`, and `login.png` are captured from a normal local run
at 1440px width, because they depend on the analyst's own workspace state.

## Refreshing these images

Re-run the script after a UI change and commit the result with the change that
caused it. A screenshot that no longer matches the product is worse than no
screenshot.
