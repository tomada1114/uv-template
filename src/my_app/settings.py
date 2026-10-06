"""Runtime configuration read from ``MY_APP_``-prefixed environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "MY_APP_"
SQLITE_URL_PREFIX = "sqlite:///"


class Settings(BaseSettings):
    """Configuration shared by every entry point.

    Pydantic belongs here because this is a deserialization boundary: strings
    from the environment become typed, validated values before the
    composition root sees them.

    Attributes:
        database_url: ``sqlite:///<path>`` selects the SQLite repository at
            that path; unset keeps to-dos in memory for the life of the
            process. Read from ``MY_APP_DATABASE_URL``.
    """

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX)

    database_url: str | None = None

    @field_validator("database_url")
    @classmethod
    def _require_sqlite_url(cls, value: str | None) -> str | None:
        """Reject any URL the composition root could not open.

        Failing here, at startup, beats failing on the first request.
        """
        if value is None:
            return None
        if not value.startswith(SQLITE_URL_PREFIX) or value == SQLITE_URL_PREFIX:
            msg = f"database_url must look like '{SQLITE_URL_PREFIX}<path>', got {value!r}"
            raise ValueError(msg)
        return value

    @property
    def sqlite_path(self) -> Path | None:
        """The SQLite file ``database_url`` names, or None for the in-memory store.

        ``sqlite:///app.db`` is relative to the working directory and
        ``sqlite:////var/lib/app.db`` is absolute, as in SQLAlchemy's URLs.
        """
        if self.database_url is None:
            return None
        return Path(self.database_url.removeprefix(SQLITE_URL_PREFIX))
