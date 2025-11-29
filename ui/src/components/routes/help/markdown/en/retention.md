# Retention in Howler

In order to comply with organizational policies, Howler is configured to purge stale alerts after a specific amount of
time. On this instance, that duration is `duration`.

## How Retention Works

Howler uses an automated retention job that runs on a configurable schedule (typically nightly) to remove
alerts that have exceeded their retention period. The system evaluates two criteria for deletion:

1. **Standard Retention**: Alerts are deleted when `event.created` exceeds the configured retention period
2. **Custom Expiry**: Alerts are deleted when the `howler.expiry` field indicates the alert should expire

An alert will be removed when **either** condition is met - whichever comes first.

## Custom Expiry (`howler.expiry`)

The `howler.expiry` field allows detection engineers to set custom retention periods for specific alerts
during ingestion. This field overrides the standard retention calculation and is commonly used when:

- Clients have requested shorter data retention periods than the deployment default
- Specific operations require time-limited data storage (e.g., a cybersecurity operation where data can
  only be retained for two weeks after ingest)
- Regulatory requirements mandate earlier deletion for certain types of data

```alert
The howler.expiry field can only shorten retention periods, not extend them. No matter
what, alerts cannot be retained longer than the system-wide retention cutoff based on event.created.
```

## Configuration

Administrators can configure retention settings in the system configuration:

```yaml
system:
  type: staging
  retention:
    limit_amount: 120      # Retention period duration
    limit_unit: days       # Time unit (days, hours, etc.)
    crontab: "0 0 * * *"   # Schedule (nightly at midnight)
    enabled: true          # Whether retention is active
```

## User Interface

To communicate retention timing to users, see the example alert below:

`alert`

In the top right, hovering over the timestamp will outline how long users have before the alert is
removed. In order to ensure compliance with policy, ensure that `event.created` matches the date the
underlying data was collected, allowing Howler to ensure data is purged in time.
