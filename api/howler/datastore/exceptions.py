from typing import Iterable, Optional

from elasticsearch.helpers.errors import ScanError

from howler.common.exceptions import HowlerException, HowlerKeyError


class SearchRetryException(HowlerException):
    pass


class DataStoreException(HowlerException):
    pass


class SearchException(HowlerException):
    pass


class SearchDepthException(HowlerException):
    pass


class ILMException(HowlerException):
    pass


class VersionConflictException(HowlerException):
    pass


class MultiKeyError(HowlerKeyError):
    def __init__(self, keys: Iterable[str], partial_output):
        super().__init__(str(keys))
        self.keys = set(keys)
        self.partial_output = partial_output


class HowlerScanError(HowlerException, ScanError):
    def __init__(self, message: str = "Something went wrong", cause: Optional[Exception] = None) -> None:
        HowlerException.__init__(self, message, cause if cause is not None else ScanError(message))
