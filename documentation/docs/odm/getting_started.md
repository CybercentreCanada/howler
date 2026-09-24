# Howler ODM Documentation

??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

This section of the site is useful for deciding what fields to place your raw data in when ingesting into Howler.

## Basic Field Types

Here is a table of the basic types of fields in our data models and what they're used for:

|Name|Description|
|:---|:----------|
| `Any` | Create an arbitrary, non-indexed value. |
| `Boolean` | Create a boolean field using legacy truthiness coercion. |
| `CaseInsensitiveKeyword` | Create a keyword using the lowercase Elasticsearch normalizer. |
| `Classification` | Create a normalized classification value. |
| `ClassificationString` | Create a validated classification stored as a plain string. |
| `Date` | Create a UTC-aware Elasticsearch date field. |
| `EmptyableKeyword` | Create a keyword that distinguishes empty strings from null. |
| `Enum` | Create a keyword restricted to an explicit set of values. |
| `FlattenedListObject` | Create a dotted-key object containing lists of JSON values. |
| `FlattenedObject` | Create a dotted-key object whose values are JSON encoded. |
| `Float` | Create a floating-point field. |
| `IndexText` | Create analyzed text without non-empty validation. |
| `Integer` | Create a bounded 32-bit Elasticsearch integer. |
| `Json` | Create a JSON-encoded keyword field. |
| `Keyword` | Create a non-empty string stored as an Elasticsearch keyword. |
| `List` | Create a typed array field. |
| `LowerKeyword` | Create a keyword normalized to lowercase. |
| `Mapping` | Create a typed dynamic-key mapping. |
| `Optional` | Create a nullable field with a null default. |
| `Text` | Create non-empty analyzed text. |
| `UUID` | Create a string identifier with a generated default. |
| `UpperKeyword` | Create a keyword normalized to uppercase. |
| `ValidatedKeyword` | Create a keyword validated by a regular expression. |

## Field States

In each table, there will be a "Required" column with different states about the field's status:

|State|Description|
|:---|:----------|
|:material-checkbox-marked-outline: Yes|This field is required to be set in the model|
|:material-minus-box-outline: Optional|This field isn't required to be set in the model|
|:material-alert-box-outline: Deprecated|This field has been deprecated in the model. See field's description for more details.|

__Note__: Fields that are ":material-alert-box-outline: Deprecated" that are still shown in the docs will still work as expected but you're encouraged to update your configuration as soon as possible to avoid future deployment issues.
