# Howler

Howler is a security alert triage and investigation platform where analysts review detections, investigate related telemetry, and organize findings into cases.

## Language

**Hit**:
An analytic or detection output representing a single finding for triage, carrying workflow state and a promotion level (`hit`, `alert`, or `evidence`).
_Avoid_: Event, Case, Bundle

**Alert**:
A Hit promoted to an escalation level that requires analyst triage and response.
_Avoid_: Raw Hit, Evidence

**Event**:
A noteworthy telemetry or observable record stored independently for investigation and correlation, without Hit triage workflow state.
_Avoid_: Hit, Alert

**Case**:
An investigation container that groups related Hits, Events, sub-cases, references, folders, and markdown notes, optionally populated by automated correlation rules.
_Avoid_: Bundle, Dossier

**Dossier**:
A query-matched presentation configuration that attaches contextual investigative leads and pivots when viewing matching Hits.
_Avoid_: Case

**Bundle**:
A deprecated legacy grouping of a parent Hit and child Hits, retained only for backward-compatibility translation into Cases.
_Avoid_: Case
