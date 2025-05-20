# Elasticsearch datastore support

This component aims to simplify the connection between your app and Elasticsearch by providing a single interface to use with all your different indices.

Advantages:

- Connection keep alive and retries
  - No need to worry if you elastic cluster goes down, your app will resume where it was when it's back online.
- Keep index management simple:
  - If you register a new index to the data, the associated index in Elastic will be created.
  - If you add or remove a field in an index, the associated index in Elastic will be updated.
  - You can easily re-index, re-shard or change and index replication.
- Support bulk operations and archiving
- Support all basic operation get, put, update, search, facet, stats, histogram...

Disadvantages:

- Search uses lucene only (covers 99% of use-cases but may be extended if needed)

## Naming convention

Take note of the different naming convention:

- An Elastic index will be refered as a `Collection` because it may have multiple indexes as it's backend
- The object that holds multiple collection as a `Datastore`

## Usage

### Instanciating a datastore

When instanciating an datastore object, there are no collection associated to it. You need to register each collection in the object so it be kept in sync and have access to it. After the collection is registered, you have access to this collection as a property of the datastore object.

Example:

```python
from howler.common import loader
from myapp.models.mymodel import MyModel

ds = loader.get_esstore()
ds.register('mymodel', MyModel)

my_document = ds.mymodel.get(document_id)

```

### Creating your own datastore

This get very complicated when you have multiple collections which is why we recommend that you create your own datastore helper class that has all collections pre-loaded.

Example:

```python
from howler.common import loader
from howler.datastore.collection import ESCollection
from howler.datastore.store import ESStore

from myapp.models.mycollection import MyCollection
# ... + all other collection


class MyDatastore(object):
    def __init__(self, esstore_object: ESStore = None ):

        self.ds = esstore_object or loader.get_esstore()
        self.ds.register('mycollection', MyCollection)
        # ... + all other collections

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ds.close()

    @property
    def mycollection(self) -> ESCollection[MyCollection]:
        return self.ds.mycollection

    # ... + all other properties tied to the different collections
```

### Collection functions

Once you've setup your own datastore object, you can start using the different functions that each collection offers. Here's a breakdown:

- `archive(query)`: Send all meatching documents to the archive of the collection
- `get_bulk_plan()`: Create a bulk plan to be executed later using the bulk function
- `bulk(bulk_plan)`: Execute the bulk plan
- `multiget(id_list)`: Get multiple documents for the id_list
- `exists(id)`: Check if a document matching this id exists
- `get(id)`: Get a document matching the id (retry twice if missing)
- `get_if_exists(id)`: Get a document matching the id (do not retry)
- `require(id)`: Try to get a document matching the id and retry forever until it exists
- `save(id, doc)`: Save a document to this id and overrite it if it exists
- `delete(id)`: Delete the document matching this id
- `delete_by_query(query)`: Delete all documents matching this query
- `update(id, operations)`: Perform the following update operation on this id
- `update_by_query(query, operations)`: Perform the following update operation all document matching this query
- `search(query)`: Find document matching the query and return one page
- `stream_search(query)`: Return all document matching the query
- `histogram(field, start, end, gap)`: Count how many documents are found in each gap from the start to the end (works on dates and int fields)
- `facet(field)`: Return the top 10 values of a field
- `stats(field)`: Generate min, max, avg, count of an int field
- `grouped_search(group_field, query)`: Find all document matching a query and group the result by this field
- `fields()`: List all fields of a collection

Management related function: (*These should not really be used in normal code but are more tailored to fix issues and test the system*)

- `commit()`: Save the indexes to disc now and make all documents available for search
- `keys()`: Return ids of all the document in the index
- `fix_ilm()`: Fix Index Lifecycle management configuration for the associated indices
- `fix_replicas()`: Fix the number of copies of the associated indices
- `fix_shards()`: Fix the number of shards of the associated indices
- `reindex()`: Reindex all documents
- `wipe()`: Delete and create empty version of this collection
