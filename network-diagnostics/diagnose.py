#!/usr/bin/env python3
"""Bounded single-host network diagnostics. No scanning or packet crafting."""
import argparse, json, platform, shutil, socket, subprocess, time

def run(host, tcp=None, ping_count=0):
    report = {"host": host, "checks": [], "platform": platform.system()}
    start = time.monotonic()
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)})
        report["checks"].append({"name":"dns", "ok":True, "addresses":addresses, "ms":round((time.monotonic()-start)*1000,1)})
    except OSError as e:
        report["checks"].append({"name":"dns", "ok":False, "error":str(e)})
        addresses=[]
    if tcp:
        t=time.monotonic()
        try:
            with socket.create_connection((host,tcp), timeout=3): pass
            report["checks"].append({"name":"tcp", "port":tcp, "ok":True, "ms":round((time.monotonic()-t)*1000,1)})
        except OSError as e: report["checks"].append({"name":"tcp", "port":tcp, "ok":False, "error":str(e)})
    if ping_count:
        ping=shutil.which("ping")
        if not ping: report["checks"].append({"name":"icmp", "ok":False, "error":"ping executable unavailable"})
        else:
            flag="-n" if platform.system()=="Windows" else "-c"
            try:
                result=subprocess.run([ping,flag,str(min(ping_count,4)),host],capture_output=True,text=True,timeout=8,check=False)
                report["checks"].append({"name":"icmp", "ok":result.returncode==0, "exit_code":result.returncode, "output":result.stdout[-1200:]})
            except subprocess.TimeoutExpired: report["checks"].append({"name":"icmp", "ok":False, "error":"timed out"})
    route=shutil.which("ip")
    if route and addresses and platform.system()!="Windows":
        result=subprocess.run([route,"route","get",addresses[0]],capture_output=True,text=True,timeout=3,check=False)
        if result.returncode==0: report["route"] = result.stdout.strip()[:1200]
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("host"); p.add_argument("--tcp",type=int); p.add_argument("--ping-count",type=int,default=0); p.add_argument("--json")
    a=p.parse_args()
    if not 0<=a.ping_count<=4 or (a.tcp is not None and not 1<=a.tcp<=65535): p.error("ping-count must be 0..4 and TCP port 1..65535")
    result=run(a.host,a.tcp,a.ping_count); output=json.dumps(result,indent=2); print(output)
    if a.json:
        with open(a.json,"w",encoding="utf8") as f:f.write(output+"\n")
