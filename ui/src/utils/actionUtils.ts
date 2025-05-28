import type { ActionOperation, ActionOperationStep } from 'models/ActionTypes';
import type { Operation } from 'models/entities/generated/Operation';

/**
 * A simple validation function to ensure we have all the necessary arguments filled out.
 * @param step The step to validate
 * @param values The context to validate on
 * @returns whether all the necessary arguments have been filled in the given step
 */
export const checkArgsAreFilled = (step: ActionOperationStep, values: string) => {
  if (!values) {
    return false;
  }

  const parsedValues = JSON.parse(values);
  return Object.keys(step.args).every(arg => !!parsedValues[arg]);
};

/**
 * Convert a raw list of keyt value pairs into a context object used in other util functions. Converts it into a list like so:
 *
 * {
 *  "key": "value"
 * }
 * is converted to:
 * ["key:value"]
 *
 * Which is the format used for conditionals throughout the action specification.
 *
 * @param values The raw values object to convert
 * @returns a list representing the current context
 */
const buildContext = (values: string = '{}') => Object.entries(JSON.parse(values)).map(tuple => tuple.join(':'));

/**
 * Take the raw options object as specified by the server and get a list of usable options, filtered using the current values suppled for the action entry.
 * @param options The raw list of options from the server
 * @param arg The argument for which we are parsing options
 * @param context The values provided so far by the user
 * @returns a list of options matching the current context
 */
export const getOptionsByContext = (
  options: ActionOperationStep['options'],
  arg: string,
  context: string
): string[] => {
  if (!options[arg]) {
    return [];
  }

  // If it's just an array, there's no special conditional logic to deal with - we just return the array
  if (Array.isArray(options[arg])) {
    return options[arg] as string[];
  }

  // Build the context up from the raw values, and check to see if any of the context values matches the conditionals provided in the options.
  // i.e.
  //
  // options = {
  //  "status:open": [] // would match if values["status"] === "open"
  // }
  //
  // Note that this restricts the options to a single key:value pair.
  // For more complex cases down the road (if those end up existing), we'll need to improve this
  const matchingKey = buildContext(context).find(key => !!options[arg][key]);

  return (options[arg][matchingKey] as string[]) ?? [];
};

/**
 * Get a list of arguments to display based on the current context, using the current values supplied for the action entry.
 * @param args a complete list of all arguments in the action
 * @param values the current list of values provided by the user
 * @returns A list of arguments to display
 */
export const getArgsByContext = (args: ActionOperationStep['args'], values: string): string[] =>
  Object.entries(args)
    .filter(([_, conditions]) => {
      // If the array is empty, we always want to show this argument
      if (conditions.length < 1) {
        return true;
      }

      const context = buildContext(values);

      // Note that the .some(...) here means the arguments are ORed together, not ANDed. So:
      // "arg_to_show": ["status:open", "assignment:goose"]
      // Will show if only one of these two conditions is valid.
      return conditions.some(c => context.includes(c));
    })
    .map(([arg, _]) => arg);

/**
 * Check to see if a given action has all the data necessary to execute successfully
 * @param data The user-provided data
 * @param action The action to validate
 * @returns whether the action is ready to execute
 */
export const operationReady = (data: Operation['data_json'], action: ActionOperation) => {
  if (!data) {
    return false;
  }

  const parsedData = JSON.parse(data);
  return (
    action &&
    getArgsByContext(
      action.steps.reduce((acc, _step) => ({ ...acc, ..._step.args }), {}),
      data
    ).every(v => !!parsedData[v])
  );
};
