package portfolio.queue

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

final class JobQueueSpec extends AnyFunSuite {
  private def queue(): (JobQueue, java.nio.file.Path) = {
    val path = Files.createTempFile("workflow-queue-", ".db")
    (new JobQueue(path.toString, maxAttempts = 3), path)
  }

  test("enqueue is idempotent and dependencies wait for successful completion") {
    val (q, _) = queue()
    val now = System.currentTimeMillis()
    val first = q.enqueue("build-1", "compile", now = now)
    assert(q.enqueue("build-1", "different payload") == first)
    val dependent = q.enqueue("deploy-1", "release", Some(first), now)
    assert(q.claim("worker-a", now).exists(_.id == first))
    assert(q.claim("worker-b", now).isEmpty)
    assert(q.complete(first, "worker-a", now + 1))
    assert(q.claim("worker-b", now + 1).exists(_.id == dependent))
  }

  test("lease expiry recovers work and retries stop at configured attempts") {
    val (q, _) = queue()
    val id = q.enqueue("retry-me", "payload", now = 100)
    assert(q.claim("dead-worker", now = 100, leaseMillis = 10).nonEmpty)
    assert(q.claim("too-early", now = 109).isEmpty)
    val recovered = q.claim("worker", now = 110).get
    assert(recovered.id == id && recovered.attempts == 2)
    assert(!q.complete(id, "dead-worker"))
    assert(q.fail(id, "worker", "retryable", now = 110))
    assert(q.claim("worker", now = 111).isEmpty)
    val exhausted = q.claim("worker", now = 1110).get
    assert(exhausted.attempts == 3)
    assert(q.fail(id, "worker", "terminal", now = 1110))
    assert(q.get(id).exists(_.state == "failed"))
  }

  test("payload and lease bounds reject invalid inputs") {
    val (q, _) = queue()
    intercept[IllegalArgumentException](q.enqueue("", "x"))
    intercept[IllegalArgumentException](q.enqueue("too-large", "x" * (1024 * 1024 + 1)))
    intercept[IllegalArgumentException](q.claim("worker", leaseMillis = 0))
  }
}
