# RomM telemetry: the metrics tree

This page lists every metric RomM sends or plans to send, where its code lives,
and which libraries we use or avoid. For how to turn telemetry on and connect a
tool, see [OPENTELEMETRY.md](OPENTELEMETRY.md).

## The rule

Telemetry measures size, speed and spread. Size is memory and CPU. Speed is how
long requests, jobs and queries take. Spread is the distribution of those
numbers (the slow end, not only the average) and how they differ between
processes.

Telemetry never carries what people look at. A metric may be labeled with a
fixed, small set of names we choose: a process role, a queue, a job function, a
route template such as `/api/roms/{id}`, a SQL verb, a provider name. It is never
labeled with a URL, a query string, SQL text, a Valkey argument, a log line, or a
ROM, platform or user name. What we do not carry cannot leak.

## The tree

Status: **built** is in the code today. **planned** is designed and not built.

```text
romm.*
├─ process.*          memory and CPU of every RomM process
│   ├─ memory         rss, pss, uss, swap                  built  handler/telemetry_handler.py
│   ├─ cpu.time       user, system                         built  handler/telemetry_handler.py
│   ├─ threads                                             built  handler/telemetry_handler.py
│   ├─ open_fds                                            built  handler/telemetry_handler.py
│   └─ disk.io        read, write                          built  handler/telemetry_handler.py
│
├─ api.*
│   ├─ worker.lifetime                                     planned
│   ├─ worker.exit_memory   rss, pss, uss, swap            planned
│   ├─ request.duration     route template, method, status class   planned
│   └─ request.in_flight                                   planned
│
├─ rq.*
│   ├─ job.peak_rss         queue, job function            built  handler/rq_worker_telemetry.py
│   ├─ job span memory      pss and uss, start and end     planned
│   ├─ horse.rss                                           built  handler/rq_worker_telemetry.py
│   ├─ queue.depth                                         built  handler/telemetry_handler.py
│   ├─ workers                                             built  handler/telemetry_handler.py
│   ├─ job.duration         queue, job function, outcome   planned
│   └─ job.wait             time spent queued              planned
│
├─ valkey.*
│   ├─ memory                                              built  handler/telemetry_handler.py
│   ├─ evicted_keys                                        built  handler/telemetry_handler.py
│   └─ keys                                                built  handler/telemetry_handler.py
│
├─ db.*
│   ├─ query.duration       SQL verb only                  planned
│   ├─ query.slow           count over a threshold         planned
│   └─ pool.in_use, pool.size                              planned
│
├─ scan.*
│   ├─ duration, roms_processed                            planned
│   └─ hash.duration                                       planned
│
└─ provider.*
    └─ request.duration, errors   provider name only       planned
```

## Libraries

| Family      | Library                                        | Metrics it makes                                                   | What we do                                                                                        |
| ----------- | ---------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| Process     | `opentelemetry-instrumentation-system-metrics` | `process.*`, `system.*`                                            | Keep the process family. `romm.process.*` covers it and adds PSS and USS. `system.*` is excluded. |
| HTTP server | `-asgi`, `-fastapi`                            | `http.server.duration`, request and response size, active requests | Off. Spans carry the URL. Replaced by `romm.api.request.duration`.                                |
| HTTP client | `-aiohttp-client`, `-httpx`, `-urllib`         | `http.client.duration`, request and response size                  | Off. This is where provider keys leak. Replaced by `romm.provider.request.duration`.              |
| Database    | `-sqlalchemy`                                  | `db.client.connections.usage`, spans with SQL text                 | Off. We build the pool numbers ourselves from SQLAlchemy pool events.                             |
| Cache       | `-redis`                                       | Spans only                                                         | Off.                                                                                              |
| Python      | part of system-metrics                         | `process.runtime.gc_count`, `thread_count`                         | Excluded. Add it back as a RomM metric if garbage collection becomes a question.                  |

The defaults are set in `docker/s6-overlay/scripts/init`.

## Open decisions

- **Allowlist.** Today the libraries above are switched off by name, so a newly
  installed instrumentation package starts on. The plan is to skip the
  `opentelemetry-instrument` wrapper and start the SDK ourselves, naming only
  what we want.
- **Groups.** The metrics split by how much they could reveal, and one setting
  could choose which are on:

  | Group       | Contents                                            | Default |
  | ----------- | --------------------------------------------------- | ------- |
  | `process`   | `process.*`, `valkey.*`, `rq.queue.*`, `rq.workers` | on      |
  | `timing`    | `api.request.*`, `rq.job.*`, `db.query.*`           | on      |
  | `providers` | `provider.*`                                        | opt in  |
  | `scan`      | `scan.*`                                            | opt in  |

- **Cost.** Request and query timing run on every request and query. Measure
  their memory and CPU before deciding what is on by default.
- **Unmatched routes** (404s) have no template. Record them as `unmatched`.
- **Socket.IO events** need their own timing if they matter.
