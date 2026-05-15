# Freelio Workers

This package owns BullMQ queue definitions, queue publishers, and worker
processors. Redis/BullMQ internals stay in Node/TypeScript.

## Queue Foundation

- Queue names live in `src/queues/constants.ts`.
- Redis configuration lives in `src/queues/redis.ts` and requires `REDIS_URL`.
- Queue creation lives in `src/queues/factory.ts`.
- Retry and retention defaults live in `src/queues/options.ts`.
- Deterministic job IDs live in `src/queues/jobIds.ts`.
- Worker payload types live in `src/types/jobs.ts`.

## API-To-Worker Bridge

FastAPI currently writes invoice send work into the `job_outbox` table. The next
integration feature should add a clean bridge owned by Node/TypeScript, such as
an outbox relay or internal queue publisher endpoint, that calls the publishers
in `src/queues/publishers`.

Python should not write BullMQ Redis keys or manually construct BullMQ Redis
data structures. PDF rendering may remain Python/WeasyPrint, but BullMQ queue
creation and job publishing should remain behind the Node/TypeScript boundary.

## Smoke Queue Support

`enqueueSmokeQueueJobs()` enqueues no-op jobs to the pdf, email, and reminder
queues. The existing FastAPI smoke API already guards smoke actions behind
`ENABLE_SMOKE_TESTS`; wiring that route to this worker-side helper is future
bridge work.
