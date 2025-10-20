# Howler ODM Documentation

??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

This section of the site is useful for deciding what fields to place your raw data in when ingesting into Howler.

## Basic Field Types

Here is a table of the basic types of fields in our data models and what they're used for:

|Name|Description|
|:---|:----------|
| `Any` | A field that can hold any value whatsoever but which is stored as a |
| `Boolean` | A field storing a boolean value. |
| `Classification` | A field storing access control classification. |
| `ClassificationString` | A field storing the classification as a string only. |
| `Date` | A field storing a datetime value. |
| `EmptyableKeyword` | A keyword which allow to differentiate between empty and None values. |
| `Enum` | A field storing a short string that has predefined list of possible values |
| `FlattenedListObject` | A field storing a flattened object |
| `FlattenedObject` | A field storing a flattened object |
| `Float` | A field storing a floating point value. |
| `IndexText` | A special field with special processing rules to simplify searching. |
| `Integer` | A field storing an integer value. |
| `Json` | A field storing serializeable structure with their JSON encoded representations. |
| `Keyword` | A field storing a short string with a technical interpretation. |
| `List` | A field storing a sequence of typed elements. |
| `Mapping` | A field storing a sequence of typed elements. |
| `Optional` | A wrapper field to allow simple types (int, float, bool) to take None values. |
| `Text` | A field storing human readable text data. |
| `UUID` | A field storing an auto-generated unique ID if None is provided |
| `UpperKeyword` | A field storing a short uppercase string with a technical interpretation. |
| `ValidatedKeyword` | Keyword field which the values are validated by a regular expression |

## Field States

In each table, there will be a "Required" column with different states about the field's status:

|State|Description|
|:---|:----------|
|:material-checkbox-marked-outline: Yes|This field is required to be set in the model|
|:material-minus-box-outline: Optional|This field isn't required to be set in the model|
|:material-alert-box-outline: Deprecated|This field has been deprecated in the model. See field's description for more details.|

__Note__: Fields that are ":material-alert-box-outline: Deprecated" that are still shown in the docs will still work as expected but you're encouraged to update your configuration as soon as possible to avoid future deployment issues.
