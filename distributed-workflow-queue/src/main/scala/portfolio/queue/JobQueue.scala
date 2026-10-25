package portfolio.queue

import java.sql.{Connection, DriverManager, ResultSet}
import scala.util.Using

final case class Job(id: Long, jobKey: String, payload: String, state: String, attempts: Int, worker: Option[String])

final class JobQueue(database: String, maxAttempts: Int = 5) {
  require(maxAttempts > 0, "maxAttempts must be positive")
  Class.forName("org.sqlite.JDBC")

  private def connection(): Connection = DriverManager.getConnection(s"jdbc:sqlite:$database")
  private def using[A](f: Connection => A): A = Using.resource(connection())(f)

  using { c =>
    val s = c.createStatement()
    try {
      s.execute("PRAGMA journal_mode=WAL")
      s.execute("PRAGMA foreign_keys=ON")
      s.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY,
        job_key TEXT NOT NULL UNIQUE,
        payload TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('pending','running','succeeded','failed')),
        attempts INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL,
        worker TEXT,
        lease_until INTEGER,
        available_at INTEGER NOT NULL,
        dependency_id INTEGER REFERENCES jobs(id),
        last_error TEXT,
        created_at INTEGER NOT NULL
      )""")
      s.execute("CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(state, available_at, id)")
    } finally s.close()
  }

  def enqueue(key: String, payload: String, dependency: Option[Long] = None, now: Long = System.currentTimeMillis()): Long = {
    require(key.nonEmpty && key.length <= 128, "job key must contain 1..128 characters")
    require(payload.getBytes("UTF-8").length <= 1024 * 1024, "payload exceeds 1 MiB")
    using { c =>
      val p = c.prepareStatement("""INSERT INTO jobs(job_key,payload,state,max_attempts,available_at,dependency_id,created_at)
        VALUES(?,?,'pending',?,?,?,?) ON CONFLICT(job_key) DO NOTHING""")
      try {
        p.setString(1, key); p.setString(2, payload); p.setInt(3, maxAttempts); p.setLong(4, now)
        dependency match { case Some(id) => p.setLong(5, id); case None => p.setNull(5, java.sql.Types.INTEGER) }
        p.setLong(6, now); p.executeUpdate()
      } finally p.close()
      val q = c.prepareStatement("SELECT id FROM jobs WHERE job_key=?")
      try { q.setString(1, key); val rs = q.executeQuery(); try { if (!rs.next()) throw new IllegalStateException("inserted job disappeared"); rs.getLong(1) } finally rs.close() }
      finally q.close()
    }
  }

  def claim(worker: String, now: Long = System.currentTimeMillis(), leaseMillis: Long = 30_000): Option[Job] = {
    require(worker.nonEmpty && worker.length <= 128, "worker must contain 1..128 characters")
    require(leaseMillis > 0, "lease must be positive")
    using { c =>
      val reap = c.prepareStatement("UPDATE jobs SET state='failed',worker=NULL,lease_until=NULL,last_error='worker lease expired after final attempt' WHERE state='running' AND lease_until<=? AND attempts>=max_attempts")
      try { reap.setLong(1, now); reap.executeUpdate() } finally reap.close()
      val p = c.prepareStatement("""UPDATE jobs SET state='running',worker=?,attempts=attempts+1,lease_until=?
        WHERE id=(SELECT j.id FROM jobs j WHERE j.attempts < j.max_attempts
          AND ((j.state='pending' AND j.available_at<=?) OR (j.state='running' AND j.lease_until<=?))
          AND (j.dependency_id IS NULL OR EXISTS(SELECT 1 FROM jobs d WHERE d.id=j.dependency_id AND d.state='succeeded'))
        ORDER BY j.available_at,j.id LIMIT 1)
        RETURNING id,job_key,payload,state,attempts,worker""")
      try {
        p.setString(1, worker); p.setLong(2, Math.addExact(now, leaseMillis)); p.setLong(3, now); p.setLong(4, now)
        val rs = p.executeQuery()
        try if (rs.next()) Some(readJob(rs)) else None finally rs.close()
      } finally p.close()
    }
  }

  def complete(id: Long, worker: String, now: Long = System.currentTimeMillis()): Boolean = using { c =>
    val p=c.prepareStatement("UPDATE jobs SET state='succeeded',worker=NULL,lease_until=NULL WHERE id=? AND state='running' AND worker=? AND lease_until>? ")
    try { p.setLong(1,id); p.setString(2,worker); p.setLong(3,now); p.executeUpdate()==1 } finally p.close()
  }

  def fail(id: Long, worker: String, reason: String, now: Long = System.currentTimeMillis(), retryDelayMillis: Long = 1_000): Boolean = {
    require(retryDelayMillis >= 0, "retry delay cannot be negative")
    using { c =>
      val p = c.prepareStatement("""UPDATE jobs SET state=CASE WHEN attempts<max_attempts THEN 'pending' ELSE 'failed' END,
        available_at=?,worker=NULL,lease_until=NULL,last_error=? WHERE id=? AND state='running' AND worker=?""")
      try {
        p.setLong(1, Math.addExact(now, retryDelayMillis)); p.setString(2, reason.take(2048)); p.setLong(3, id); p.setString(4, worker)
        p.executeUpdate() == 1
      } finally p.close()
    }
  }

  def get(id: Long): Option[Job] = using { c =>
    val p = c.prepareStatement("SELECT id,job_key,payload,state,attempts,worker FROM jobs WHERE id=?")
    try { p.setLong(1,id); val rs=p.executeQuery(); try if(rs.next()) Some(readJob(rs)) else None finally rs.close() } finally p.close()
  }

  private def readJob(rs: ResultSet): Job = Job(rs.getLong(1),rs.getString(2),rs.getString(3),rs.getString(4),rs.getInt(5),Option(rs.getString(6)))
}
