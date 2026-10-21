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

    def preflight(self, datastore: "HowlerDatastore") -> None:
        """Perform read-only validation before any selected migration starts.

        Preflights must not initialize protected lazy collections, mutate
        datastore state, or acquire/release migration claims. The runner calls
        them as a batch before executing any selected migration.
        """
        return None

    @abstractmethod
    def run(self, datastore: "HowlerDatastore") -> int:
        """Apply the migration and return the number of affected documents."""
        raise NotImplementedError
