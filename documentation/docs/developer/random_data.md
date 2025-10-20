# Generating Random Data

To get an idea of what Howler looks like with data, and to test your code, you can use the helper file
`howler/odm/random_data.py`. It contains methods for generating test data for all models used in howler:

```shell
cd ~/repos/howler-api

# Run without arguments, all models are wiped and populated with test data
python howler/odm/random_data.py

# You can also choose specific indexes to populate
python howler/odm/random_data.py users hits analytics
```
