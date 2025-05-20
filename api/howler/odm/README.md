# Object Data Model (ODM) Support

To ensure that the data in your application is always of the right type and is always saved in a normalize way, you can use the ODM to define how your data is structured. The ODM also works in conjunction with the datastore to automatically create associated Elasticsearch indices that will match your data and provide you with the best search experience.

## Define a new Model

When defining a new model object to be used in the system, you must create a class the inherit from the `odm.Model` class and use the `@odm.model()` decorator to set some default class parameters. Each parameters of your model object has to be of type `odm._Field`. You can find out about the different types of field in a section below.

Here's example of a user model with settings and stats:

```python
from howler import odm

@odm.model(index=True, store=False, description="Settings of user")
class Settings(odm.Model):
    default_view: str = odm.Enum(value=['detail', 'simple'], default='simple', description="Some random setting")

@odm.model(index=True, store=False, description="Settings of user")
class Stats(odm.Model):
    last_login: str = odm.Date(default='NOW', description="Last time user logged in")
    login_count: str = odm.Integer(default=0, description="Number of time the user logged in")

@odm.model(index=True, store=True, description="User example")
class User(odm.Model):
    username: str = odm.Keyword(description="Username of the user")
    password: str = odm.Keyword(description="Password of the user")
    settings: Settings = odm.Compound(Settings, default={}, description="User's settings")
    stats: Stats = odm.Compound(Stats, default={}, description="User's statistics")
```

As a YAML representation, this model would look like this:

```yaml
username: ...
password: ...
settings:
  default_view: simple
stats:
  last_login: '2022-06-21T03:33:37.452270Z'
  login_count: 0
```

### Model class decorator options

There are 3 options you can pass to the object class decorator:

- `index`: Default index value for the field inside the object class
- `store`: Default store value for the field inside the object class
- `description`: Description of the object class (used by auto markdown documentation)

### Generic field options

There are 5 generic options that all fields can take:

- `index`: Should Elastic index the values of that field (inherit from class default if not set)
- `store`: Should the value of that field be returned in the default search response (inherit from class default if not set)
- `copyto`: Which field to copy the value into for easier search
- `default`: Default value for this field
- `description`: Description of the field (used by auto markdown documentation)

***Note***: Some fields that are more complex may use options.

### Supported field types

Here is the list of supported field type and their extra options if any:

- `odm.Date`: A field storing an ISO date (if the default value is set to NOW, it will be the time the field get created)
- `odm.Boolean`: A field storing a boolean and is normalized using the python `bool()` function.
- `odm.Keyword`: A field storing a string with strict search values and is normalized using the `str()` function.
  - `odm.EmptyableKeyword`: An `odm.Keyword` field that allow `None` values.
  - `odm.LowerKeyword`: An `odm.Keyword` field that is always saved in lowercase mode.
  - `odm.UpperKeyword`: An `odm.Keyword` field that is always saved in uppercase mode.
  - `odm.ValidatedKeyword(regex)`:  An `odm.Keyword` validated by a regular expression.
    - `odm.IP`: A validated IP field stored as IP in Elastic to allow CIDR queries.
    - `odm.Domain`: A validated domain field
    - `odm.Email`: A validated email address field
    - `odm.URI`: A validated URI field
    - `odm.URIPath`: A validated URI path field
    - `odm.MAC`: A validated Mac address field
    - `odm.PhoneNumber`: A validated Phone Number field
    - `odm.SSDeepHash`: A validated SSDeep hash field indexed in two parts to allow proximity searches
    - `odm.SHA1`: A validated SHA1 hash field
    - `odm.SHA256`: A validated SHA256 hash  field
    - `odm.MD5`: A validated MD5 hash  field
    - `odm.Platform`: A validated Plaform field
    - `odm.Processor`: A validated Processor field
  - `odm.Classification`: A field storing access control classification.
  - `odm.ClassificationString`: A field storing the classification as a string only.
  - `odm.Enum(values)`: A field storing short string form a list of possible values
  - `odm.UUID`: A field storing an auto-generated unique ID if none is provided
- `odm.Json`: A field storing a JSON serialized string and is normalized using the `json.dumps()` function.
- `odm.Text`: A field storing human readable text data
- `odm.IndexText`: A special field with special processing rules to simplify searching.
- `odm.Integer`: A field storing an integer value.
- `odm.Float`: A field storing a floating point value.
- `odm.List(child_object)`: A field storing a sequence of `odm._Field` or `odm.Model`.
- `odm.Mapping(child_object)`: A field storing a dictionary of `odm._Field`.
  - `odm.FlattenedListObject(child_object)`: An `odm.Mapping` field storing a list of flattened `odm.Json` objects.
  - `odm.FlattenedObject(child_object)`: A `odm.Mapping` field storing a flattened `odm.Json` object.
- `odm.Compound(child_type)`: A field storing a second level `odm.Model` object.
- `odm.Any`: A field that store the data as is and does not try to validate it. (never indexed, never stored)
- `odm.Optional(child_object)`: A wrapper field to allow simple types to take None values.
