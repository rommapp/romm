# Monitoring RomM with OpenTelemetry

RomM can send metrics over OpenTelemetry (OTLP), the open standard most
monitoring tools accept. This page explains what RomM sends, how to turn it on,
and how to read the memory numbers.

Telemetry is off by default. RomM sends nothing, and does no telemetry work,
until you set at least one `OTEL_` environment variable.

## What RomM sends

RomM's telemetry is about size, speed and spread: how much memory and CPU each
process uses, and how those numbers vary. It does not record what people look
at: no URLs or query strings, no SQL text, no Valkey arguments, no log lines,
and no ROM, platform or user names.

Several OpenTelemetry instrumentation libraries do record those things, and some
metadata providers send their API key in the request URL. RomM turns these off
by default: `aiohttp-client`, `asgi`, `fastapi`, `httpx`, `redis`, `requests`,
`sqlalchemy`, `urllib` and `urllib3`. Log export is off as well. To opt back in,
set `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS` to the list you still want
disabled, and `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true` for logs.
The OTLP endpoint and headers are credentials themselves, so keep them out of
shared configuration.

Every part of RomM runs as its own process, and each one reports under its own
service name:

| Service name          | Process                                                           |
| --------------------- | ----------------------------------------------------------------- |
| `api`                 | The web API, as a gunicorn master and its workers.                |
| `rq_worker`           | The background worker for the `high`, `default` and `low` queues. |
| `rq_scan_worker`      | The background worker that runs library scans.                    |
| `rq_streaming_worker` | The streaming worker. It only runs when streaming is on.          |
| `rq_cron`             | The scheduler for recurring tasks.                                |
| `watcher`             | The file watcher that notices changes in the library.             |
| `sync_watcher`        | The sync folder watcher. It only runs when it is enabled.         |
| `startup`             | The short task that runs once when the container starts.          |

To tell RomM apart from other apps in a shared tool, set
`OTEL_SERVICE_NAME_PREFIX`. With `OTEL_SERVICE_NAME_PREFIX=romm-`, the API
reports as `romm-api`.

### Metrics

| Metric                     | What it measures                                                                                                                                         |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `romm.process.memory`      | The memory of every RomM process in the container, in bytes. The `process.memory.kind` attribute says which number it is: `rss`, `pss`, `uss` or `swap`. |
| `romm.process.cpu.time`    | The CPU time every RomM process has used, in seconds, split by `cpu.mode` into `user` and `system`.                                                      |
| `romm.process.threads`     | The threads in every RomM process.                                                                                                                       |
| `romm.process.open_fds`    | The open files and sockets in every RomM process.                                                                                                        |
| `romm.process.disk.io`     | The bytes every RomM process has read and written, split by `disk.io.direction`.                                                                         |
| `romm.rq.job.peak_rss`     | The highest memory the work horse of a job reached, in bytes. A histogram recorded as the job ends, so it also catches jobs that last a few seconds.     |
| `romm.rq.horse.rss`        | The memory of each running work horse, in bytes, sampled by its worker.                                                                                  |
| `romm.rq.queue.depth`      | The jobs waiting in each queue.                                                                                                                          |
| `romm.rq.workers`          | The number of background workers that are running.                                                                                                       |
| `romm.valkey.memory`       | The memory Valkey uses, its peak, and its limit, in bytes.                                                                                               |
| `romm.valkey.evicted_keys` | The keys Valkey removed to stay under its memory limit.                                                                                                  |
| `romm.valkey.keys`         | The number of keys in each Valkey database.                                                                                                              |

The `romm.process.*` metrics and the Valkey and queue gauges are read once per
export by the `rq_cron` process, so they are not repeated by every worker.

The `romm.process.*` metrics carry three attributes that tie each
operating-system process to the part of RomM it is:

- `romm.process.role`: the part of RomM the process runs, such as `api` or
  `rq_scan_worker`.
- `romm.process.kind`: what the process is within that part, such as `parent`,
  `scheduler` or `work_horse`.
- `process.parent_pid`: the pid of the process that started it.

The standard system-metrics library also sends `process.memory.usage`,
`process.cpu.time` and `process.thread.count` for each instrumented process.

#### Which process is which

A role can have several processes, because some parts of RomM fork children.

| Role                                                 | Kind               | What it is                                                                                                     |
| ---------------------------------------------------- | ------------------ | -------------------------------------------------------------------------------------------------------------- |
| `api`                                                | `master`           | The gunicorn master. It serves no requests; it starts and replaces the workers.                                |
| `api`                                                | `worker`           | One of the API workers, 4 by default (`WEB_SERVER_CONCURRENCY`).                                               |
| `rq_worker`, `rq_scan_worker`, `rq_streaming_worker` | `parent`           | The long-lived RQ worker process that waits for jobs on its queues.                                            |
| same                                                 | `scheduler`        | The worker's scheduler, which releases delayed jobs. Forked once at start-up, and lives as long as its parent. |
| same                                                 | `work_horse`       | The process that runs one job. Forked when a job starts, exits when it ends.                                   |
| `rq_cron`                                            | `main`             | Puts scheduled tasks on their queues. Forks nothing.                                                           |
| `nginx`                                              | `master`, `worker` | nginx's master process and its workers.                                                                        |
| `valkey`                                             | `main`             | The internal Valkey server, when no external one is configured.                                                |
| `watcher`, `sync_watcher`                            | `main`, `worker`   | `watchfiles` (`main`) and the Python script it runs (`worker`).                                                |

The kind is decided by `process_kind` in
[`backend/utils/process_stats.py`](../backend/utils/process_stats.py): a process
whose parent has a different role is the role's first process. A child of an RQ
worker is a `work_horse` if it leads its own process group, which RQ sets up
right after the fork, and a `scheduler` otherwise. Any other child is a `worker`.

For chart legends, join the code's names to the pid, so a line reads like
`rq_scan_worker work_horse (pid 412)`:

```text
{romm_process_role} {romm_process_kind} (pid {process_pid})
```

#### Which memory number to use

- **RSS** counts every page the process can see, including pages it shares with
  other processes. Adding RSS across processes counts shared memory more than
  once, so the total is too high.
- **PSS** splits each shared page evenly between the processes that share it.
  The sum of PSS across processes is the real memory RomM uses.
- **USS** counts only the pages no other process has. It is the memory you would
  get back by stopping that one process.

Use PSS for the total, USS for the cost of one process, and RSS to compare with
`ps` or `top`. PSS and USS are only available on Linux, which includes the RomM
Docker image.

USS is misleading for a process that has just forked a child. Right after a
fork, every page is shared between parent and child, so neither counts it as
its own. To see whether such a process grew, compare its RSS.

A work horse is a fork of its worker, so `romm.rq.job.peak_rss` includes the
pages they share.

## Turning it on

Add these variables to the `romm` service in your `docker-compose.yml`, and
replace the endpoint with the address of your tool:

```yaml
services:
  romm:
    environment:
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318
      - OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
      - OTEL_SERVICE_NAME_PREFIX=romm-
```

Then recreate the container with `docker compose up -d`. A plain
`docker restart` keeps the settings the container was created with, so it
doesn't apply changed variables.

### Turning it off

To switch telemetry off without deleting your settings, add
`OTEL_SDK_DISABLED=true` and recreate the container. With telemetry off, no
process is started through `opentelemetry-instrument`, RomM loads none of its
telemetry code, and nothing is sent. `false`, or leaving the variable out,
means on again, as long as another `OTEL_` variable is set.

### Choosing a protocol

| Protocol       | Usual port | `OTEL_EXPORTER_OTLP_PROTOCOL` | Endpoint form      |
| -------------- | ---------- | ----------------------------- | ------------------ |
| OTLP over HTTP | 4318       | `http/protobuf`               | `http://host:4318` |
| OTLP over gRPC | 4317       | `grpc`                        | `http://host:4317` |

If you leave `OTEL_EXPORTER_OTLP_PROTOCOL` out, RomM uses `grpc`. Pointing a
`grpc` client at an HTTP port fails with connection errors in the RomM logs, so
always set the protocol.

### Authentication

Most hosted tools need a key, which you pass as a header, writing any space as
`%20`. Keep keys out of `docker-compose.yml` if you share it. Put them in your
`.env` file instead, or use a Docker secret.

```yaml
- OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20<base64 credentials>
```

### Settings RomM chooses for you

When telemetry is on, RomM sets these variables unless you set them yourself:

| Variable                                           | RomM's value                 | Why                                                                    |
| -------------------------------------------------- | ---------------------------- | ---------------------------------------------------------------------- |
| `OTEL_EXPERIMENTAL_RESOURCE_DETECTORS`             | `otel,process`               | Adds `process.pid` to every metric. Command lines are not sent.        |
| `OTEL_PYTHON_SYSTEM_METRICS_EXCLUDED_METRICS`      | `system.*,process.runtime.*` | Leaves out machine-wide metrics, which every process would send again. |
| `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS`            | See above                    | Keeps URLs, SQL text and Valkey arguments out of telemetry.            |
| `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED` | `false`                      | Keeps log lines, which can contain a URL, out of telemetry.            |

## Metric names in different tools

OpenTelemetry names use dots, such as `romm.rq.horse.rss`. Tools change them:
Prometheus-style tools turn dots into underscores and add the unit, so
`romm.rq.job.peak_rss` can appear as `romm_rq_job_peak_rss_bytes`. If a query
finds nothing, look for the renamed metric.

## What telemetry costs

Measuring memory takes some memory, so RomM only loads its telemetry code when
telemetry is on. With telemetry on, each instrumented process loads the
OpenTelemetry SDK and exporters, which costs tens of MB per long-lived process.
Measure on your own container with `romm.process.memory` before and after.

## Known limits

- The `romm.process.*` metrics only see processes in RomM's own container. A
  database or Valkey that runs in a separate container is not included.
- Processes that run as another user, in practice nginx's workers, are left out
  of the `romm.process.*` metrics unless the container has the `SYS_PTRACE`
  capability, because Linux won't let the telemetry read their memory.
- A process that has exited stays on per-process charts for up to 5 minutes.
  OpenTelemetry pushes metrics and never marks a series as ended, so the chart
  keeps the last value for the query's lookback window.
- RomM sends no request timings, query timings or traces. Planned metrics are
  listed in [TELEMETRY_METRICS.md](TELEMETRY_METRICS.md).

## For contributors: keep telemetry off when it is off

Every telemetry feature in RomM follows three rules, so that people who never
turn telemetry on never pay for it:

1. Check `config.OTEL_ENABLED`. It is on when any `OTEL_` variable is set,
   unless `OTEL_SDK_DISABLED` is true.
2. Put the feature in its own module with `telemetry` in its name, such as
   `handler/rq_worker_telemetry.py` or `handler/telemetry_handler.py`.
3. Import that module only inside an `if OTEL_ENABLED:` block, at the point of
   use.

`test_without_otel_no_process_loads_romm_telemetry` in
`backend/tests/tasks/test_task_func_paths.py` starts the API, the worker, the
scheduler and the file watcher with telemetry off, and fails if any of them
loads a RomM module with `telemetry` in its name, or the OpenTelemetry
instrumentation package.
