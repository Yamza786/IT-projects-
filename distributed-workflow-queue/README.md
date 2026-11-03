# Distributed Job Queue and Workflow Engine

A Scala/JDBC job queue backed by SQLite WAL. It supports idempotent enqueue keys, prerequisite jobs, ordered atomic claims, expiring worker leases, bounded payloads and retry limits. SQLite's conditional `UPDATE … RETURNING` makes claiming atomic across competing processes sharing the database.

## Run

Install JDK 17+ and sbt, then run `sbt test`. Construct `new JobQueue("queue.db")`, call `enqueue(key, payload, optionalDependency)`, poll `claim(workerId)`, and acknowledge with `complete` or `fail`. A failed attempt is retried after its delay until the configured attempt limit is reached.

## Operations and limits

Keep the database on a local filesystem with reliable locking. SQLite is suitable for a single host and modest queue volume; this is not a multi-host broker. Workers must make side effects idempotent because a crashed worker's expired lease can cause redelivery. Jobs with failed dependencies remain unclaimable and need operator intervention. The sample stores opaque UTF-8 payloads, not secrets or executable code.

## Contributing and license

Run `sbt test` before changes and add tests for state transitions and concurrency behavior. Licensed under the repository MIT license.
