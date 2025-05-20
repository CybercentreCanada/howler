from howler.odm.models.action import VALID_TRIGGERS

OPERATION_ID = "example_plugin"


def execute(query: str, arg1: str, arg2: str, **kwargs):
    """This function is called either when triggered manually or any of the accepted triggers are met.

    Args:
        query (str): The query this action is running on
        arg1 (str, optional): The provided value for the matching argument below. One of "a", "b", "c".
        arg2 (str, optional): The provided value for the matching argument below. Freeform text.
    """
    report = []

    try:
        # Do whatever you want here - make requests, parse them, etc.

        # There are three types of responses you can add to the report - success, skipped and error.
        if arg1 in ["a", "c"]:
            report.append(
                {
                    "query": query,
                    "outcome": "success",
                    "title": "Executed Successfully",
                    "message": "Example action ran successfully!",
                }
            )
        else:
            report.append(
                {
                    "query": query,
                    "outcome": "skipped",
                    "title": "Execution Skipped",
                    "message": "Since arg1 was b, we didn't run the action.",
                }
            )
    except Exception as e:
        report.append(
            {
                "query": query,
                "outcome": "error",
                "title": "Failed to Execute",
                "message": f"Unknown exception occurred: {str(e)}",
            }
        )

    return report


def specification():
    """A function that returns information about how to present the action in the UI.

    This information includes what information must be provided, and how the UI should ask for it, as well as basic
    data validation.
    """
    return {
        "id": OPERATION_ID,
        # The string to use if no localization is available
        "title": "Example Plugin",
        # If you have a localization key in the UI, set it here.
        "i18nKey": f"operations.{OPERATION_ID}",
        # Provide a short and long description. These must be useful - they'll be presented to users in the UI.
        "description": {
            "short": "Just an example plugin implementation",
            "long": execute.__doc__,
        },
        # What roles should be necessary to run this action? In general, automation_basic should always be required,
        # while automation_advanced should be set when this action could be dangerous or costly in terms of resources.
        "roles": ["automation_basic"],
        # What data should the user be required to provide? This is split intop steps, so arguments can depend on each
        # other, giving basic control flow for specifying arguments.
        "steps": [
            {
                # A list of argument values the user must provide in this step
                "args": {"arg1": []},
                # Specifying a matching key corresponding to a list of strings in options will allow users to choose
                # from a  pre-defined list of values, while not providing it will allow them to enter any freeform text.
                "options": {"arg1": ["a", "b", "c"]},
                # You can specify "warn" and "error" validation queries. The UI will pop up a warning or error if this
                #  query returns a match when ANDed with the supplied query. i.e. say the query they are running the
                # action on is "howler.id:*" and they have chosen "a" for arg1, then
                # if the query "howler.id:* AND howler.labels.generic:*a*" has any matches, this will warn the user.
                "validation": {
                    "warn": {
                        # The query to match against. Basic replacement works, i.e. $<var_name> =>
                        # replaced with the value for var_name.
                        "query": "howler.labels.generic:*$arg1*",
                        # What message should be shown? This is optional - a generic message will be shown otherwise
                        "message": "You can't have a label that contains the character chosen as arg1!",
                    }
                },
            },
            {
                # This means that the UI for adding an input for arg2 will only be required if arg1 is "a" or "b",
                # not "c".
                "args": {"arg2": ["arg1:a", "arg1:b"]},
                # No options provided => freeform text
                "options": {},
            },
        ],
        # What triggers should one be able to use this action with? In this case, we allow all of them.
        "triggers": VALID_TRIGGERS,
    }
