# Gallery

Every screen image lives here: real captures of the running Seclyst console, and
the original interface of each of the five tools, one folder per tool.

## The running product

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

### Regenerating

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

Re-run the script after a UI change and commit the result with the change that
caused it. A screenshot that no longer matches the product is worse than no
screenshot.

## Each engine's original interface

These are captures of the original tools as they were before they were brought
into Seclyst. They document what each engine can do and where its screens came
from.

### Malware Analyzer

| Image | Shows |
| --- | --- |
| `malware/MalwareAnalyzer-Dashboard.png` | The analyzer's landing dashboard |
| `malware/Upload.png` | Sample upload |
| `malware/Analysis.png` | The analysis view for a submitted sample |
| `malware/MalwareAnalyzer-Result.png` | The consolidated result |
| `malware/PE-Analysis.png` | PE structure inspection |
| `malware/Script-Analysis.png` | Script payload inspection |
| `malware/Processes.png` | Observed process activity |
| `malware/Sandbox.png` | Sandbox report |
| `malware/IOCs.png` | Extracted indicators |
| `malware/ThreatIntel.png` | Threat-intelligence enrichment |
| `malware/VT.png` | VirusTotal panel |
| `malware/API.png` | Provider API configuration |
| `malware/Other-Apis.png` | Additional provider configuration |
| `malware/Scoring.png` | Risk scoring breakdown |

### Phishing Detector

| Image | Shows |
| --- | --- |
| `phishing/PhishingMail-Dashboard.png` | The detector's landing dashboard |
| `phishing/Upload.png` | Mail upload |
| `phishing/PhishingMail-Result.png` | The consolidated verdict |
| `phishing/Auth.png` | SPF, DKIM, and DMARC results |
| `phishing/Raw-Header.png` | Raw header inspection |
| `phishing/Signs.png` | Detected phishing indicators |
| `phishing/Artifacts.png` | Extracted URLs and attachments |
| `phishing/Text-View.png` | Rendered message text |
| `phishing/Html-View.png` | Rendered HTML body |

### Event Analyzer

| Image | Shows |
| --- | --- |
| `events/EventAnalyzer-Dashboard.png` | The analyzer's landing dashboard |
| `events/Upload.png` | EVTX upload |
| `events/EventAanalyzer-Result.png` | The consolidated result (filename typo is original) |
| `events/Events-Detail.png` | Event detail view |
| `events/IOCs.png` | Indicators extracted from the log set |
| `events/Sigma-rule.png` | Sigma rule listing |
| `events/Sigma-Event-Detail.png` | Events matched by one Sigma rule |
| `events/Triggered-Evetns-Sigma.png` | Triggered rules (filename typo is original) |
| `events/Notes.png` | Analyst notes |

## Adding images

Put product captures at the top level of this folder, and engine captures under
the engine's folder with a row added to its table. Keep the original filename
where it came from a tool's own repository so provenance stays traceable.
