---
name: wait
description: Wait for a background job to complete
model: haiku
---

Wait for the following background job or condition:

$ARGUMENTS

Check status at reasonable intervals. Do not poll more frequently than every 30 seconds.
Maximum wait time: 270 seconds. If the job is not done by then, report its last known status.

Do not use this skill for polling loops longer than 270 seconds.
