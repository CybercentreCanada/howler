# Using Actions in Howler

Actions are a feature in Howler that allow users to perform particular tasks on a large number of hits, through automating the execution of a task on each hit. There are currently `action_count` operations supported in howler:

`action_list`

All of these operations can be combined together into unique actions - that is, operations are essentially the building blocks of actions in Howler. Each operation can only appear once per action, and all operations are configured through one unified UI. In this document, we will walk through the steps necessary to run and save an action.

## Configuring an Action

In order to begin configuring your action, decide if this will be a one-off action or a saved action you want to run several times. If you want to run it once, use the `t(route.actions.change)` entry in the sidebar, while a saved action is best configured under the `t(route.actions.manager)` by pressing "`t(route.actions.create)`".

The first step of any action will be to design a query on which you want this action to run. The search box at the top of the accepts any lucene query - the same format as searching for hits.

`tui_phrase`

Once you are satisfied with the hits that will be included in this query, you can begin adding operations. You can do so by selecting the operation you want to add from the dropdown:

`operation_select`

Once you've selected the operation you want to add, it will prompt you for a list of parameters you will need to fill out. Below is an example for adding a label.

`operation_configuration`

Once the operation validates successfully, you can repeat this process with the next operation. Once you've added all the operations you're interested in, you can execute or save the action using the button below the search bar. This will generate a report of the steps taken.

`report`

Occaisionally, actions will result in an error, either on validation or on execution. In these cases, an error alert will be shown, helping you solve the issue.

## Automating an Action

In order to automate an action, open any saved action. The options available to you for automation (`automation_options`) will show up as checkboxes. Checking the box will ensure this action will run then - no further work required.
