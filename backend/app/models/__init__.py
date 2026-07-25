"""Cross-cutting ORM models.

Imported here so `Base.metadata` is fully populated wherever any `app.models.*`
submodule is imported — required for Alembic autogenerate and for tests that call
`Base.metadata.create_all()` directly.
"""

from app.models.base import Base
from app.models.configuration import Configuration
from app.models.organisation import Organisation

__all__ = ["Base", "Configuration", "Organisation"]
