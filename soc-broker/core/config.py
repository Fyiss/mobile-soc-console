import yaml
from dataclasses import dataclass, field


@dataclass
class MQTTConfig:
    host: str = "localhost"
    port: int = 1883
    topic_alerts: str = "soc/alerts"
    topic_commands: str = "soc/commands"


@dataclass
class AuthConfig:
    secret_key: str = "change-me-in-production"
    token_expire_minutes: int = 60


@dataclass
class Config:
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    host: str = "0.0.0.0"
    port: int = 8000

    @classmethod
    def load(cls, path: str) -> "Config":
        try:
            with open(path) as f:
                raw = yaml.safe_load(f) or {}
        except FileNotFoundError:
            raw = {}

        mqtt_raw = raw.get("mqtt", {})
        auth_raw = raw.get("auth", {})

        return cls(
            mqtt=MQTTConfig(**{k: v for k, v in mqtt_raw.items()
                               if k in MQTTConfig.__dataclass_fields__}),
            auth=AuthConfig(**{k: v for k, v in auth_raw.items()
                               if k in AuthConfig.__dataclass_fields__}),
            host=raw.get("host", "0.0.0.0"),
            port=raw.get("port", 8000),
        )
