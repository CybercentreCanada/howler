# Utility Functions

The `howler/common` folder provides the utility functions for the library. Each file inside this folder will be explained in this README.

## chunk.py

Has utilities to transform list of items into list of tuples grouping sets of X items together.

- `chunk(list)`: The chunk function return a generator of tuples.

- `chunked_list(list)`:

    The chunked_list goes through all the items and returns a list of all the tuples.

        chunked_list([1,2,3,4,5,6,7,8], 2): [(1,2), (3,4), (5,6), (7,8)]

## classification.py

This file, in conjunction to it's default configuration file `classification.yml`, provide support for handling classifications in the system (Access control). It is fully configurable and the configuration definition is provided in-line in the `classification.yml` file.

### Classification object

The classification object provides the different methods to parse, normalize and compare classification strings. Here are some notable functions you will likely be using:

- `list_all_combinations()`: This function returns all possible classification strings that the current `classification.yml` file supports.
- `get_access_control_parts()`: This functions splits the classification string in parts to be used in a lucene query.
- `intersect_user_classification(c12n_1, c12n_2)`: This function takes two classification strings and generate the highest classification that both strings share in common.
- `is_accessible(user_c12n, target_c12n)`: This function verifies if a user's maximum classification give them access to see a certain target classification.
- `max_classification(c12n_1, c12n_2)`: This function returns the highest possible classification by mixing both classifications.
- `min_classification(c12n_1, c12n_2)`: This function returns the minimum possible classification by mixing both classifications.

## dict_utils.py

This file provides utility functions to merge dictionaries together, find the differences between dictionaries or change the ways its keys are displayed.

- `strip_nulls(dict)`: This function remove all keys that are null in the dictionary rescursively.
- `recursive_update(dict, update_dict)`: This function recursively applied the update_dict values to the original dict that was provided
- `get_recursive_delta(d1, d2)`: This function generate a delta dictionary that tells you which keys changed to which values if you go from d1 to d2.
- `flatten/unflatten(dict)`:

    The flatten function take a multiple level deep dictionary and transforms it into a single level dictionary by preserving the key space using a dotted notation:

        {a: {b: 1} }: {a.b: 1}

    Where as the unflatten does the invert by taking the dotted notation and transforming it back to it's original multiple level dictionary.

## hexdump.py

This file provide functions to take a binary data blob and transform it into and hexadecimal dump of its bytes. The `dump(buf)` function only outputs the bytes where as the `hexdump(buf)` function outputs also the offsets and some trimmed down ascii representation.

`dump("HTTP/1.1 404 Not\r\nCont")`

    48 54 54 50 2F 31 2E 31 20 34 30 34 20 4E 6F 74 20 46 6F 75 6E 64 0D 0A 43 6F 6E 74

`hexdump("HTTP/1.1 404 Not\r\nCont")`

    00000000:  48 54 54 50 2F 31 2E 31 20 34 30 34 20 4E 6F 74  HTTP/1.1 404 Not
    00000010:  20 46 6F 75 6E 64 0D 0A 43 6F 6E 74              Found..Cont

## iprange.py

This file provides you with a RangeTable class that let's you determine if and IP is part of a certain CIDR definition. It also provides to quick function that let you determine if an IP is in a private CIDR (`is_private(ip)`) or if an IP is in a reserved CIDR (`is_reserved(ip)`).

*Note*: only IPV4 IPs are supported.

## isotime.py

This file provides you which methods to transform date into strings or epoch values. It support local, ISO and epoch time. It also makes sure that the local and ISO time get up to a microsecond precision.

Here are the support date operation:

- Get current time functions:
  - `now()` -> Current epoch time
  - `now_as_iso()` -> Current iso time
  - `now_as_local()` -> Current local time
- Tranformation functions:
  - `epoch_to_iso(date)`
  - `epoch_to_local(date)`
  - `local_to_epoch(date)`
  - `local_to_iso(date)`
  - `iso_to_epoch(date)`
  - `iso_to_local(date)`

## loader.py

This file provide helper function for components that require external configuration files: Classification engine, datastore and remote datatypes.

- `get_classification()`: returns a pre-configured classification object.
- `get_config()`: returns the current classification of the system.
- `get_datastore()`: returns an Howler datastore using the config form the get_config() output.

## log.py/logformat.py

This file provides an `init_logger()` function that will setup logging in your app using the configuration file and formats it using the format found in logformat.py

## memory_zip.py

Provides an interface file to create zip files in memory.

## net.py/net_static.py

Provide multiple function to validate ip/port/domains and the get networking information about the current host.

- Validation:
  - `is_valid_port(port)`
  - `is_valid_domain(domain)`
  - `is_valid_ip(ip)`
  - `is_valid_email(email)`
  - `is_ip_in_network(ip, cidr)`
- Network information:
  - `get_hostname()`
  - `get_mac_address()`
  - `get_route_to(ip)`
  - `get_host_ip()`
  - `get_host_default_gateway()`

## random_user.py

Generate random usernames base of a list of nouns and adjectives.

## security.py

Provide secure function to generate/validate passwords and API keys of users.

- Password generation/validation:
  - `get_password_hash(password)`: returns the hash of a plaintext password
  - `verify_password(password, hash)`: verifies if a password matches a hash
  - `get_random_password()`: generates a random password
  - `check_password_requirements(password)`: Check if a password meets the minimum requirements

## str_utils.py

Provide functions to safely manipulate and transform strings.

- `safe_str(buf)`: Make sure to safely encode bytes into uft-8 string or change the current string encoding to utf-8
- `translate_str(buf)`: Try to guess the current encoding of a string or a byte buffer
- `truncate(buf)`: Make sure a string does not exceed a certain length by adding ellipses.

## uid.py

Generate random ID in a format shorter then UUID and more double click friendly

- `get_random_id()`: Generate a, base62 based + 22 character, collision free random ID
- `get_id_from_data(data)`: Generate an ID base of the provided data
