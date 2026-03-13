# Mobile SOC Console — Linux Agent

Detection + response agent for the Phone-Controlled Intrusion Response System.

## Architecture

```
soc-agent/
├── agent.py                  # Entry point
├── config.yaml               # Configuration
├── requirements.txt
├── core/
│   ├── config.py             # Config loader
│   ├── event_bus.py          # Async event bus (SecurityEvent, ResponseCommand)
│   └── broker_client.py      # MQTT publisher/subscriber
├── monitors/
│   ├── ssh_monitor.py        # SSH brute force detection (journald)
│   ├── process_monitor.py    # Suspicious process detection
│   ├── network_monitor.py    # Port scan + suspicious connections
│   └── log_monitor.py        # Generic regex-based log rules
└── responders/
    └── dispatcher.py         # Executes: block_ip, kill_process, isolate, dismiss
```

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Optional: install Mosquitto broker
sudo pacman -S mosquitto
sudo systemctl enable --now mosquitto
```

## Run

```bash
# Needs root for iptables response actions + reading some logs
sudo python agent.py
```

Without root: detection still works, but `block_ip` and `isolate` will fail.

## Event Types

| Event | Severity | Trigger |
|-------|----------|---------|
| `ssh_bruteforce` | high | 5+ SSH failures from same IP in 60s |
| `ssh_bruteforce_ongoing` | critical | Continues past threshold |
| `suspicious_process` | high/critical | Known bad process name or cmdline pattern |
| `suspicious_connection` | high | Outbound to known bad ports (4444, 1337, etc.) |
| `port_scan` | high | 15+ unique ports from same IP in 10s |
| `log_sudo_failure` | medium | sudo auth failure in logs |
| `log_su_attempt` | medium | su failure |
| `log_kernel_exploit_attempt` | critical | ptrace/kallsyms access in logs |

## Response Commands (from mobile app via MQTT)

```json
{
  "action": "block_ip",
  "target": "192.168.1.5",
  "event_id": "a1b2c3d4",
  "authorized_by": "phone-device-id"
}
```

| Action | Target | Effect |
|--------|--------|--------|
| `block_ip` | IP address | iptables DROP in+out |
| `unblock_ip` | IP address | Remove iptables rule |
| `kill_process` | PID (string) | SIGKILL |
| `isolate` | (ignored) | Full network isolation |
| `dismiss` | (ignored) | Acknowledge, no action |

## Next Steps

- [ ] Backend broker (FastAPI + Mosquitto)
- [ ] Mobile app (Flutter) with push notifications
- [ ] TLS mutual auth between agent and broker
- [ ] Persistent alert log / SQLite
- [ ] systemd service file for agent
