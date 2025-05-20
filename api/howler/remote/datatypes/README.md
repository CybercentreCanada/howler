# Remote Datatypes

Now that most project are distributed using containers there is sometimes a need for having data structures available live to different process running on different hosts. This is where the remote datatypes com into play. These are essentially data structures stored in Redis that are available to all processes in your cluster.

We have a various range of supported data types to account to various scenarios:

## Counters

Counters are very useful to gather metrics throughout your system.

They support simple integer operation:

- `inc(name, x)`: Increment name counter by X
- `dec(name, x)`: Decrement name counter by X
- `set(name, x)`: Set name counter to X

They also have other functions to inspect the values:

- `get_queues()`: List the name of all the counters
- `get_queues_sizes()`: List the name of all the counters with their current sizes
- `reset_queues()`: Reset all counters to 0
- `delete()`: Delete any traces to the counters

Example:

```python
from howler.remote.datatypes.counters import Counters
with Counters('test-counter') as ct:
    # Increment counter by 4
    ct.inc('value_1', 4)

    # Get Counter values
    ct.get_queues_sizes()
```

Output:

```json
{
  "test-counter-value_1": 4
}
```

## Event Senders/Watchers

Event senders and watchers are use to trigger code execution on multiple container when another container performs an action. If multiple containers register to watch the same event, they will all receive the same message when the event fires.

Methods:

- EventSender:
  - `send(event_name, event_data)`: Sends the event_data as an event of type event_name
- EventWatcher:
  - `register(event_name, callback)`: Register a callback function for all events of type event name (wildcard * can be use to register a single callback to multiple events)
  - `start()`: Start listening for events
  - `stop()`: Stop listening for events

Example, A container register a watcher for a specific event:

```python
import time
from howler.remote.datatypes.events import EventWatcher

def callback_func(data: dict[str, Any]):
    print(data)

watcher = EventWatcher()
try:
    # register for the test event in the event group
    watcher.register('event.test', callback_func)
    watcher.start()
    while True:
        time.sleep(1)
finally:
    watcher.stop()

```

Another container creates an event to wake up the first container:

```python
import time
from howler.remote.datatypes.events import EventSender

# create a sender for the event group
sender = EventSender('event.', redis_connection)

# send a test even
sender.send('test', {'payload': 100})
# After this call, the first container will have woken up and executed its callback function
# that would print: {'payload': 100}
```

## Hash Table

Hash tables are used to keep dictionary like structures available to all containers in your cluster.

They support the following methods:

- `add(key, value)`: Add the specified value to the key in the hash table, if the key already exists it is not added
- `increment(key, count)`: Increment the value at the key by the count
- `limited_add(key, value, limit)`: Add the specified value to the key in the hash table, if size of the set is smaller then the limit
- `exists(key)`: Check if a get exists
- `get(key)`: Get the value at the specfied key
- `keys()`: Return the list of keys in the hash table
- `length()`: Return the number of keys in the hash table
- `items()`: Get the whole hash table keys and values as a dictionary
- `conditional_remove(key, value)`: Remove the key from the hash table if it value is the same as specified
- `pop(key)`: Get the value of the key and remove it from the hash table
- `set(key, value)`: Set the specified key to a specific value
- `multi_set(dict)`: Set multiple keys at once
- `delete()`: Completely delete the hash structure

Example:

```python
from howler.remote.datatypes.hash import Hash
with Hash('test-hashmap') as h:
    h.add("key", "value")
    print(h.exists("key"))
    print(h.get("key"))
    print(h.items())
```

Output:

```python
True
"value"
{"key": "value"}
```

## Global Locks

If you need to make sure that certain set of operation do not take place at the same time in two different processes/containers/threads, you can use the global lock.

The global lock can only be used using a `with` statement and specifies the max amount of time you can keep the lock for.

Example:

```python
from howler.remote.datatypes.lock import Lock

def process_1():
    with Lock('test', 10):
        # Do sensitive execution up to 10 seconds

def process_2()
    with Lock('test', 20):
        # Do sensitive execution up to 20 seconds

# Process 2 has to wait that process 1 is done before executing
```

## Sets

Sets are very useful to keep a list of non-duplicated items available to all containers in your cluster.

They support the following methods:

- `add(value1, ...)`: Add one or many values to the set
- `limited_add(value, limit)`: Add a value only if the number of items already in is smaller then the limit
- `remove(value)`: Remove a specific value from the set
- `exist(value)`: Check if a value exists in the set
- `pop()`: Returns a random value from the set and removes it
- `pop_all()`: Returns all values from the set and removes them all
- `random()`: Return a random member of the set but keeps it in the set
- `members()`: Return all members from the set and leave them there
- `length()`: Returns the length of the set
- `delete()`: Deletes the set entirely

Example:

```python
from howler.remote.datatypes.set import Set
with Set('test-set') as s:
    values = ['a', 'b', 1, 2]
    s.add(*values)
    print(s.exist('b'))
    print(s.pop())
    print(s.length())
```

Output:

```python
True
'a' or 'b' or 1 or 2
3
```

## Quota trackers

Quota trackers are used to track user quotas in the system. It has only two functions, one to start tracking an operation and another to end it. If the begin of tracking returns false, the user is over it's quota.

Methods:

- `begin(unique_identifier, max_quota)`: Increment the current quota of the unique identifier if its not already at the maximum, returns `False` if over the quota.
- `end(unique_identifier)`:  Decrease the current quota of the unique identifier

Example:

```python
from howler.remote.datatypes.user_quota_tracker import UserQuotaTracker
uqt = UserQuotaTracker('test-quota')

try:
    ok = uqt.start('uid', 3):
    if ok:
        # Do processing which has quota
    else:
        raise Exception('Over your quota...')

finally:
    if ok:
        uqt.end('uid')
```

## Queues

To support distributed processing in a container based environment, this library also support multiple queuing types so the containers can pass messages from one to another.

### Comunication queues

Communication queues are similar to a chat where user connected receive the message but do not know of the message that happened while they were offline.

Available methods:

- `close()`: Stop listening for messages and disconnect from the queue
- `listen(blocking)`: This is a generator that either wait for message or return None
- `publish(message)`: Sends a message to the comms queue

Example of message receiver:

```python
from howler.remote.datatypes.queues.comms import CommsQueue

with CommsQueue('test-comms-queue') as cq:
    for msg in cq.listen(blocking=True):
        if msg == "stop":
            break

        print(message)
```

Example of message sender:

```python
from howler.remote.datatypes.queues.comms import CommsQueue

with CommsQueue('test-comms-queue') as cq:
    # send a message to the receiver
    cq.publish("This is my message!")

    # tell the receiver to stop
    cq.publish("stop")
```

### Named queues (FIFO)

Named queues are essentially First-in First-out (FIFO) queue where messages are processed in order in which they are sent in the queue.

The following methods are available:

- `delete()`: Delete the queue with all it's messages
- `length()`: Return the lenght of the queue
- `peek_next()`: Get the next item in the queue without removing it
- `pop_batch(count)`: Get X amount of items from the queue
- `pop(blocking)`: Get the next item from the queue. If blocking is True, wait for the next message
- `push(msg_1, ...)`: Push message(s) to the queue
- `unpop()`: Put the message back at the head of the FIFO queue

Example:

```python
from howler.remote.datatypes.queues.named import NamedQueue, select
with NamedQueue('test-named-queue') as nq:
    for x in range(5):
        nq.push(x)

    print(nq.pop_batch(100))
```

Output:

```python
[0, 1, 2, 3, 4]
```

### Priority queues

Priority queues are queues where the message can set its priority on insertion to determine its position in the queue. Message of the same priority will act as FIFO queues.

The following methods are available:

- `count(lowest, highest)`: Count the number of item between the lowest and highest priority (inclusive)
- `delete()`: Delete the queue with all it's items
- `length()`: Return the full length of the queue
- `pop(num)`: Pop the specified number of items form the queue
- `blocking_pop(timeout, low_priority)`: Pop the next item from the queue and wait for it if the queue is empty (low_priority pops from lower priority items first)
- `dequeue_range(lower_limit, upper_limit)`: Dequeue a number of elements, within a specified range of scores
- `push(priority, message)`: Push a message at a given priority
- `rank(message)`: Returns the priority of a message in the queue
- `remove(message)`: Removes a message from the queue by its value
- `unpush(num)`: Pop the specified number of lower priority items from the queue

Example:

```python
from howler.remote.datatypes.queues.priority import PriorityQueue, length, select
with PriorityQueue('test-priority-queue') as pq:
    for x in range(10):
        pq.push(100, x)

    a_key = pq.push(101, 'a')
    z_key = pq.push(99, 'z')
    print(pq.rank(a_key))
    print(pq.rank(z_key))
    print(pq.pop())
```

Output:

```python
0
11
'a'
```

#### Unique Priority queues

Unique Priority queues function the same way as Priority queues execept that all messages in the queue must be unique so new messages with the same value are not added again.

Example:

```python
from howler.remote.datatypes.queues.priority import PriorityQueue, length, select
with PriorityQueue('test-priority-queue') as pq:
    for x in range(10):
        pq.push(100, x)

    print(pq.length())

    # These values were already added in the previous loop so they wont be added again.
    for x in range(10):
        pq.push(100, x)

    print(pq.length())
```

Output:

```python
10
10
```
