from howler import odm

TRIGGER_TYPES = ["http", "pubsub", "datasource", "timer", "other"]


@odm.model(index=True, store=True, description="Details about the function trigger.")
class Trigger(odm.Model):
    request_id = odm.Optional(odm.Keyword(description="The ID of the trigger request , message, event, etc."))
    type = odm.Optional(odm.Enum(values=TRIGGER_TYPES, description="The trigger for the function execution."))


@odm.model(
    index=True,
    store=True,
    description="The user fields describe information about the function as a "
    "service (FaaS) that is relevant to the event.",
)
class FAAS(odm.Model):
    coldstart = odm.Optional(odm.Boolean(description="Boolean value indicating a cold start of a function."))
    execution = odm.Optional(odm.Keyword(description="The execution ID of the current function execution."))
    id = odm.Optional(odm.Keyword(description="The unique identifier of a serverless function."))
    name = odm.Optional(odm.Keyword(description="The name of a serverless function."))
    trigger = odm.Optional(odm.Compound(Trigger, description="Details about the function trigger."))
    version = odm.Optional(odm.Keyword(description="The version of a serverless function."))
