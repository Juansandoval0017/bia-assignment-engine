from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .settings import get_setting


class SnowflakeConfigurationError(RuntimeError):
    """La configuración requerida para conectarse no está completa."""


@dataclass(frozen=True)
class SnowflakeConfig:
    account: str
    user: str
    password: str
    warehouse: str
    database: str
    schema: str
    role: str | None = None

    @classmethod
    def from_environment(cls) -> "SnowflakeConfig":
        required = {
            "account": get_setting("SNOWFLAKE_ACCOUNT"),
            "user": get_setting("SNOWFLAKE_USER"),
            "password": get_setting("SNOWFLAKE_PASSWORD"),
            "warehouse": get_setting("SNOWFLAKE_WAREHOUSE"),
            "database": get_setting("SNOWFLAKE_DATABASE"),
            "schema": get_setting("SNOWFLAKE_SCHEMA"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            names = ", ".join(f"SNOWFLAKE_{name.upper()}" for name in missing)
            raise SnowflakeConfigurationError(
                f"Faltan variables de entorno de Snowflake: {names}"
            )
        return cls(**required, role=get_setting("SNOWFLAKE_ROLE"))


class SnowflakeClient:
    def __init__(self, config: SnowflakeConfig | None = None):
        self.config = config or SnowflakeConfig.from_environment()

    def connect(self) -> Any:
        try:
            import snowflake.connector
        except ImportError as error:
            raise RuntimeError(
                "Instala la integración con: pip install -e \".[snowflake]\""
            ) from error

        connection_options = {
            "account": self.config.account,
            "user": self.config.user,
            "password": self.config.password,
            "warehouse": self.config.warehouse,
            "database": self.config.database,
            "schema": self.config.schema,
        }
        if self.config.role:
            connection_options["role"] = self.config.role
        return snowflake.connector.connect(**connection_options)

    def execute_schema(self, schema_path: Path) -> None:
        """Ejecuta únicamente el SQL de tablas propias del motor."""
        statements = schema_path.read_text(encoding="utf-8").split(";")
        with self.connect() as connection:
            with connection.cursor() as cursor:
                for statement in statements:
                    statement = statement.strip()
                    if statement and not statement.startswith("--"):
                        cursor.execute(statement)
