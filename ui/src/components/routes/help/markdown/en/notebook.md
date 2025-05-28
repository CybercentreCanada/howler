# Notebook Integration

Howler provides the option to add notebooks to analytics to aid in triaging hits and alerts. It allows users to quickly spin up a notebook within a jupyter environment with either analytic and/or hit information.

Howler will look for variables to replace within the first code cell of a notebook, giving the flexibility of providing context within the first cells using markdown.

Here an example of how howler will replace the variables within your notebook:

```notebook tab="Template"
{
  "cells": [
    {
      "cell_type": "code",
      "id": "fe6f810f-2459-4ad7-92ac-1e925ce892d4",
      "outputs": [],
      "source": [
        "howlerHitId = \"{{hit.howler.id}}\"\n",
        "howlerAnalyticId = \"{{analytic.analytic_id}}\""
      ]
    },
    {
      "cell_type": "code",
      "id": "586470ef-c8e6-45b1-bd17-17ccd083eef1",
      "outputs": [],
      "source": [
        "from howler_client import get_client\n\n",
        "howler = get_client(\"$CURRENT_URL\")\n",
        "hit = howler.hit(howlerHitId)"
      ]
    }
  ],
  "nbformat": 4,
  "nbformat_minor": 5
}
```

```notebook tab="Processed"
{
  "cells": [
    {
      "cell_type": "code",
      "id": "fe6f810f-2459-4ad7-92ac-1e925ce892d4",
      "outputs": [],
      "source": [
        "howlerHitId = \"7dxHCat0Y2Sj48qyU7ZkVV\"\n",
        "howlerAnalyticId = \"2SXKl6Cq4rOxWLps2SFHyB\""
      ]
    },
    {
      "cell_type": "code",
      "id": "586470ef-c8e6-45b1-bd17-17ccd083eef1",
      "outputs": [],
      "source": [
        "from howler_client import get_client\n\n",
        "howler = get_client(\"$CURRENT_URL\")\n",
        "hit = howler.hit(howlerHitId)"
      ]
    }
  ],
  "nbformat": 4,
  "nbformat_minor": 5
}
```

or with some markdown in the first cell:

```notebook tab="Template"
{
  "cells": [
    {
      "cell_type": "markdown",
      "id": "e17cbaa8-9849-462f-9bd2-bf30943f76b3",
      "source": [
        "### Example Notebook"
      ]
    },
    {
      "cell_type": "code",
      "id": "fe6f810f-2459-4ad7-92ac-1e925ce892d4",
      "outputs": [],
      "source": [
        "howlerHitId = \"{{hit.howler.id}}\"\n",
        "howlerAnalyticId = \"{{analytic.analytic_id}}\""
      ]
    },
    {
      "cell_type": "code",
      "id": "586470ef-c8e6-45b1-bd17-17ccd083eef1",
      "outputs": [],
      "source": [
        "from howler_client import get_client\n\n",
        "howler = get_client(\"$CURRENT_URL\")\n",
        "hit = howler.hit(howlerHitId)"
      ]
    }
  ],
  "nbformat": 4,
  "nbformat_minor": 5
}
```

```notebook tab="Processed"
{
  "cells": [
    {
      "cell_type": "markdown",
      "id": "e17cbaa8-9849-462f-9bd2-bf30943f76b3",
      "source": [
        "### Example Notebook"
      ]
    },
    {
      "cell_type": "code",
      "id": "fe6f810f-2459-4ad7-92ac-1e925ce892d4",
      "outputs": [],
      "source": [
        "howlerHitId = \"7dxHCat0Y2Sj48qyU7ZkVV\"\n",
        "howlerAnalyticId = \"2SXKl6Cq4rOxWLps2SFHyB\""
      ]
    },
    {
      "cell_type": "code",
      "id": "586470ef-c8e6-45b1-bd17-17ccd083eef1",
      "outputs": [],
      "source": [
        "from howler_client import get_client\n\n",
        "howler = get_client(\"$CURRENT_URL\")\n",
        "hit = howler.hit(howlerHitId)"
      ]
    }
  ],
  "nbformat": 4,
  "nbformat_minor": 5
}
```

Currently, howler will only try to replace hit and analytic objects.

# Requirements for the notebook integration to work

- A working NBGallery setup is required.
  - If the user can send a notebook from nbgallery to their jupyter environment, it will also work using the open in jupyhub button on Howler.
- Just like with NBGallery, the user needs to make sure their Jupyter Environment is currently running, otherwise Howler will fail to open the notebook.

Howler will append the id of the Hit/Alert when sending a notebook to Jupyter, making it easy to track for analysis. It is possible to open a notebook from within an analytic page, in this case, no hit id will be appended to the file name of the notebook and Howler won't be able to replace hit informations in the templated notebook since no hit was provided.

# Adding a notebook to an analytic

To add a notebook to an analytic, it's only necessary to provide the NBGallery link of the notebook. The link shoud look like this. The notebook shouldn't be private, otherwise, only the user that uploaded it will be able to use it on Howler.

```
$NBGALLERY_URL/notebooks/5-example
```

```alert
It is advised to clear any outputs from a notebook before adding it on NBGallery to avoid leaking sensitive data.
```
