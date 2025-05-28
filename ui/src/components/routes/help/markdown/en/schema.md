# Hit Schema

A howler hit can contain a large number of unique fields, each with a particular definition, in order to make hits across analytics mutually intelligible. Below is a table containing all the given hit fields, as well as their type and a short description of what they are used for. While the vast majority of the fields are based on the Elastic Common Schema (see [here](https://www.elastic.co/guide/en/ecs/8.5/index.html) for documentation), there are also custom fields for Howler.

## Howler Fields - Best Practices

In order to allow for some consistency between various analytics, there are a number of fields with recommended (but not required) styles. These include:

- `howler.analytic`: Denotes the overarching analytic that generated the hit. For example, if the name of your analytic is Bad Guy Finder, you can set this field to Bad Guy Finder. Examples of use:

  - Bad Guy Finder (correct)
  - BadGuyFinder (acceptable, but spaces are preferred)
  - bad.guy.finder (incorrect, don't use periods)
  - bad_guy_finder (incorrect, don't use underscores)
  - in general, you can use [this regex](https://regexr.com/7ikco) to validate your proposed analytic name

- `howler.detection`: Denotes the specific algorithm or portion of the analytic that generated the hit. For example, if your analytic has three ways of detecting hits that should be looked at (Impossible Travel, Incorrect Login Information, XSS Attack Detection), then the manner in which the hit you're creating was detected should be set. Examples of use:
  - Impossible Travel (correct)
  - ImpossibleTravel (acceptable, but spaces are preferred)
  - impossible.travel (incorrect, don't use periods)
  - impossible_travel (incorrect, don't use underscores)
