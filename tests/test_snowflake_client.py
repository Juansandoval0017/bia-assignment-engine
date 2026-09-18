import pytest

from app.snowflake_client import SnowflakeConfig, SnowflakeConfigurationError


def test_snowflake_config_reads_environment(monkeypatch):
    values = {
        "SNOWFLAKE_ACCOUNT": "account",
        "SNOWFLAKE_USER": "user",
        "SNOWFLAKE_PASSWORD": "password",
        "SNOWFLAKE_WAREHOUSE": "warehouse",
        "SNOWFLAKE_DATABASE": "database",
        "SNOWFLAKE_SCHEMA": "schema",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    config = SnowflakeConfig.from_environment()

    assert config.account == "account"
    assert config.schema == "schema"


def test_snowflake_config_reports_missing_variables(monkeypatch):
    monkeypatch.setattr("app.settings.load_dotenv", lambda: None)
    monkeypatch.delenv("SNOWFLAKE_ACCOUNT", raising=False)

    with pytest.raises(SnowflakeConfigurationError, match="SNOWFLAKE_ACCOUNT"):
        SnowflakeConfig.from_environment()
