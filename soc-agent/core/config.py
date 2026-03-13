import yaml
import socket
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class BrokerConfig:
    host: str = "localhost"
    port: int = 1883
    topic_alerts: str = "soc/alerts"
    topic_commands: str = "soc/commands"
    username: str = ""
    password: str = ""
    tls: bool = False


@dataclass
class Config:
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    monitors: Dict[str, Any] = field(default_factory=dict)
    hostname: str = ""

    @classmethod
    def load(cls, path: str) -> "Config":
        try:
            with open(path) as f:
                raw = yaml.safe_load(f) or {}
        except FileNotFoundError:
            raw = {}

        broker_raw = raw.get("broker", {})
        broker = BrokerConfig(**{k: v for k, v in broker_raw.items()
                                  if k in BrokerConfig.__dataclass_fields__})

        return cls(
            broker=broker,
            monitors=raw.get("monitors", {}),
            hostname=raw.get("hostname", socket.gethostname()),
        )