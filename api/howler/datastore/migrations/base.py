from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from howler.datastore.howler_store import HowlerDatastore


class Migration(ABC):
    """A repeatable datastore migration.

    Implementations must be safe to retry. A retry can happen after a process
    failure or when a migration made a partial change before failing.
    """

    migration_id: ClassVar[str]

    @abstractmethod
    def run(self, datastore: "HowlerDatastore") -> int:
        """Apply the migration and return the number of affected documents."""
        raise NotImplementedError
