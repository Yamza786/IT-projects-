# Network Diagnostic & Troubleshooting Toolkit

Small, bounded checks for DNS resolution, TCP reachability, ICMP reachability, and route display. It produces JSON output suitable for attaching to a support ticket.

## Run

```sh
python diagnose.py example.com --tcp 443 --json report.json
python diagnose.py example.com --ping-count 2
```

DNS and TCP use Python's standard library. Ping is invoked with a fixed argument list and a short timeout; route display uses `ip route` when available. You can run DNS/TCP checks without ping. Use only against a host you are permitted to troubleshoot. This tool does not scan ports or networks.
