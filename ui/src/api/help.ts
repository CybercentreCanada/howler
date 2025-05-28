import { hget, joinUri, uri as parentUri } from 'api';

export const uri = () => {
  return joinUri(parentUri(), '');
};

interface ApiDescription {
  /**
   * Name of the api
   */
  name: string;

  /**
   * API path
   */
  path: string;

  /**
   * Is UI only API
   */
  ui_only: boolean;

  /**
   * Allowed HTTP methods
   */
  methods: string[];

  /**
   * API documentation
   */
  description: string;

  /**
   * Unique ID for the API
   */
  id: string;

  /**
   * Function called in the code
   */
  function: string;

  /**
   * Does the API require login
   **/
  protected: boolean;

  /**
   * Type of users allowed to use API
   */
  required_type: string[];

  /**
   * Type of privileges needed by API keys to use API
   */
  required_priv: string[];

  /**
   * Is the API stable?
   **/
  complete: boolean;
}

export interface HelpResponse {
  apis: ApiDescription[];
  blueprints: { [index: string]: string };
}

export const get = (): Promise<HelpResponse> => {
  return hget(uri());
};
