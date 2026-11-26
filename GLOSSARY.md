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
=======
Howler is a triage and investigation platform for security alerts (hits), events and cases.

**Annotation**:
A structured insight attached to exactly one hit or event (optionally to one field, or a substring of that field's value), stored separately from the record it describes. Its schema follows the Annotated Insight Model (AIM).
_Avoid_: Comment (that is the free-text `howler.comment` list on a record), note, enrichment annotation

**Enrichment annotation**:
Clue enrichment output rendered alongside a field or attached to a case item; unrelated to an Annotation.
_Avoid_: Annotation (unqualified)

**Opinion**:
An annotation's analytical stance on its target: a qualitative label (criteria, sentiment, factor) and a quantified rating (concern or assurance, on a 1 to 5 scale) with a confidence.
_Avoid_: Verdict, assessment

**Weight**:
The signed numeric strength of an opinion, derived from its rating and confidence.
_Avoid_: Score (that belongs to the hit or event)

**Concern**:
The total positive weight of the annotations that count towards a hit or event.
_Avoid_: Risk (that is a posture sentiment)

**Assurance**:
The total negative weight of the annotations that count towards a hit or event.
_Avoid_: Trust, confidence

**Score**:
How consequential a hit's or event's annotations say it is: concern plus assurance, multiplied by efficacy. Belongs to the record, never to an annotation.
_Avoid_: Weight, enrichment score (the deprecated `howler.score`)

**Ambiguity**:
How much a record's concern and assurance conflict, multiplied by efficacy; high ambiguity can point to a wrong opinion or to an adversary using legitimate assets.
_Avoid_: Uncertainty, confidence

**Tier**:
When a hit or event should be actioned, from 0 (will not be actioned) to 6 (notify operations and action immediately). It is calculated from score and ambiguity, which can only reach tier 5; tier 6 can only be set by hand.
_Avoid_: Priority (unqualified), severity

**Tier override**:
A tier an analyst sets by hand, with a reason, that takes precedence over the calculated tier without replacing it.
_Avoid_: Manual score

**Descriptor**:
A framework classification of what an annotation describes, such as a MITRE ATT&CK technique.
_Avoid_: Tag, label

**Efficacy**:
How far the outcome of the annotated activity is known (successful, unknown, partial, failed, blocked).
_Avoid_: Outcome (that is one part of efficacy), result

**Source method**:
The kind of producer that created an annotation: detection, enrichment, inference, routine, or analyst.
_Avoid_: Origin, author type

**Verdict**:
A peer or agent's vote supporting or refuting an annotation, with an optional justification.
_Avoid_: Opinion, review

**Annotation link**:
The reference from an annotation to its target: record type and ID, optional dotted field path and optional substring range, serialised as `$hit:<id>:dotted.path:start-end`.
_Avoid_: Pointer, anchor

**Stale annotation**:
An annotation whose captured value no longer matches the current value at its link.
_Avoid_: Broken annotation, orphan
