export const missingContext = (contextName: string): never => {
  throw new Error(`${contextName} must be used within its provider.`);
};
