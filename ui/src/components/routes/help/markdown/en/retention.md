# Retention in Howler

In order to comply with organizational policies, Howler is configured to purge stale alerts after a specific amount of time. On this instance, that duration is `duration`.

Howler calculates whether it is time for the removal of an alert by the `event.created` date - once this surpasses the confgured deadline, a nightly automated job will remove the alert.

In order to communicate this to the user, see the example alert below:

`alert`

In the top right, hovering over the timestamp will outline how long users have before the alert is removed. In order to ensure compliance with policy, ensure that `event.created` matches the date the underlying data was collected, allowing howler to ensure data is purged in time.

```alert
This will soon change - there will be a dedicated field to set that will override this approach.
```
