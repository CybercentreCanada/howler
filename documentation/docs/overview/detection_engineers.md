# Detection Engineers

You have just written an analytic that detects some suspicious activity and you would like your Security Operations Center (SOC) to benefit from it. In Howler, an event of interest is called a hit. The term alert is reserved for hits that require triage.

To create a new hit, produce a JSON object in which you have normalized the event data to Elastic Common Schema. We do this so that triage analysts have a single schema to learn regardless of the source of alerts - this will make their job much easier.

Next, you need to populate some fields specific to Howler:

- `howler.detection` - A short, unique identifier for the specific detection.
- `howler.analytic` - The actual product doing detection. Some analytics will run many distinct detections.
- `howler.outline.threat` - The identifier that best represents the attacker. This could be an IP, email address, etc...
- `howler.outline.target` - The identifier that best represents the victim. Again, an IP, domain, email address, etc...
- `howler.outline.indicators` - A free-form list of indicators of compromise (IoC). These are typically IPs, domains and hashes.
- `howler.outline.summary`- An executive summary explaining the activity that is being detected. Describe the event with the assumption that the detection is correct.
- `howler.data` - A list of dictionaries of the raw event before normalization. This makes it easier for analysts if they need to take their investigation outside of Howler.

Howler uses escalation levels (`howler.escalation`) to categorise hits:

- `miss` - The event is assessed to not be related to detection (false-positive).
- `hit` - (default) The event might not be very reliable without additional context.
- `alert` - The event should be assessed by a triage analyst.
- `evidence` - The event was assessed as related to the detection (true-positive).

You may promote some hits to alert immediately at creation time if the expectation is that all hits will be worth triaging.

Once you have completed the JSON object, use the Howler client to create a new hit. That hit will be immediately available to triage analysts from the Howler UI.

## Bundles

A bundle is a logical grouping of hits that should be assessed together. For example, if a series of multiple hits happen on the same host within a short window of time, a triage analyst should perform a single investigation that takes them all into account. The Howler UI provides a workflow for intuitively working with these bundles.

Bundles are implemented as hits that have the howler.is_bundle field set to true, and howler.hits contains a list of howler.id values. This means that analytics can be created to look for related hits and bundle them.

## Analytics Page

The Analytics section of the Howler UI provides a support page for analytics and individual detections. It contains useful information for both the author of a analytic or detection as well as the triage analysts who are investigating the hits.

### Overview

Here, you are encouraged to provide documentation in Markdown. This should provide more details about how the analytic or detection works, what it's looking for and how to validate the hits.

Metrics are automatically generated to give insights on the performance. A very high false-positive rate might be a sign that detection needs improvement. On the other hand, a high true-positive rate might warrant that hits be automatically promoted to alerts.

### Comments

In this tab, users can leave feedback about an analytic or detection. Consider this your end-user's line of communication with you.

### Hit Comments

From here, you can review all of the comments left on specific hits to better understand what triage analysts are signaling to each other.

### Notebooks

If your triage analysts are frequently needing to investigate alerts outside of Howler, you can link to a Jupyter Notebook. That means a button will appear in the Howler UI. When a user clicks the button, they will be taken to JupyterHub with the specified Notebook open and the specific hit loaded, allowing the queries to be pre-populated with relevant values.
