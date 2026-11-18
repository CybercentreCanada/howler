import json
import time
from typing import Generic, Optional, TypeVar

import redis
from pydantic import BaseModel, TypeAdapter

from howler.common.exceptions import HowlerTypeError
from howler.remote.datatypes import get_client, retry_call

T = TypeVar("T")


class NamedQueue(Generic[T]):
    def __init__(
        self, name: str, host=None, port=None, private: bool = False, ttl: int = 0, *, model: type[T] | None = None
    ):
        self.c: redis.Redis | redis.StrictRedis | redis.RedisCluster = get_client(host, port, private)
        self.name: str = name
        self.ttl: int = ttl
        self.last_expire_time: float = 0
        self._adapter: TypeAdapter[T] | None = TypeAdapter(model) if model is not None else None

    def _deserialize(self, message: str | bytes) -> T:
        if self._adapter is not None:
            return self._adapter.validate_json(message)
        return json.loads(message)

    def _serialize(self, message: T) -> str:
        if self._adapter is not None:
            return self._adapter.dump_json(message, warnings="error").decode("utf-8")
        if isinstance(message, BaseModel):
            return message.model_dump_json()
        return json.dumps(message)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.delete()

    def _conditional_expire(self):
        if self.ttl:
            ctime = time.time()
            if ctime > self.last_expire_time + (self.ttl / 2):
                retry_call(self.c.expire, self.name, self.ttl)
                self.last_expire_time = ctime

    def delete(self):
        retry_call(self.c.delete, self.name)

    def __len__(self):
        return self.length()

    def length(self):
        return retry_call(self.c.llen, self.name)

    def peek_next(self) -> Optional[T]:
        response = retry_call(self.c.lrange, self.name, 0, 0)

        if response:
            return self._deserialize(response[0])
        return None

    def pop_batch(self, size: int) -> list[T]:
        response = retry_call(self.c.lpop, self.name, size)

        if not response:
            return []

        return [self._deserialize(message) for message in response]

    def pop(self, blocking: bool = True, timeout: int = 0) -> Optional[T]:
        if blocking:
            response = retry_call(self.c.blpop, self.name, timeout)
        else:
            response = retry_call(self.c.lpop, self.name)

        if not response:
            return None

        if blocking:
            return self._deserialize(response[1])
        else:
            return self._deserialize(response)

    def push(self, *messages: T):
        raw_messages = [self._serialize(message) for message in messages]
        retry_call(self.c.rpush, self.name, *raw_messages)
        self._conditional_expire()

    def unpop(self, *messages: T):
        """Put all messages passed back at the head of the FIFO queue."""
        for message in messages:
            retry_call(self.c.lpush, self.name, self._serialize(message))
        self._conditional_expire()


def select(*queues, **kw):
    timeout = kw.get("timeout", 0)
    if len(queues) < 1:
        raise HowlerTypeError("At least one queue must be specified")
    if any([not isinstance(q, NamedQueue) for q in queues]):
        raise HowlerTypeError("Only NamedQueues supported")

    c = queues[0].c
    response = retry_call(c.blpop, [q.name for q in queues], timeout)

    if not response:
        return response

    name = response[0].decode("utf-8")
    queue = next(queue for queue in queues if queue.name == name)
    return name, queue._deserialize(response[1])
