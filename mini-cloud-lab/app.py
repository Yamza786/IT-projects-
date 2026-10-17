"""Tiny standard-library HTTP service for container/health-check practice."""
from http.server import BaseHTTPRequestHandler,HTTPServer
import json, os, sqlite3, time
START=time.time(); DB=os.environ.get("LAB_DB","/data/lab.db")
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path=="/health": payload={"status":"ok","uptime_seconds":round(time.time()-START)};status=200
  elif self.path=="/": payload={"service":"mini-cloud-lab","endpoints":["/health","/visits"]};status=200
  elif self.path=="/visits":
   os.makedirs(os.path.dirname(DB),exist_ok=True);c=sqlite3.connect(DB);c.execute("CREATE TABLE IF NOT EXISTS visits(count INTEGER)");c.execute("INSERT INTO visits VALUES(1)");c.commit();count=c.execute("SELECT COUNT(*) FROM visits").fetchone()[0];c.close();payload={"visits":count};status=200
  else: payload={"error":"not found"};status=404
  raw=json.dumps(payload).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
 def log_message(self,*args):pass
if __name__=="__main__":HTTPServer(("0.0.0.0",int(os.environ.get("PORT","8090"))),Handler).serve_forever()
