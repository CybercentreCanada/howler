/* eslint-disable no-console */
import { Paper, Table, TableBody, TableCell, TableHead, TableRow } from '@mui/material';
import AppListEmpty from 'commons/components/display/AppListEmpty';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import { flatten } from 'flat';
import Handlebars from 'handlebars';
import { capitalize, get, groupBy, isNil, isObject } from 'lodash-es';
import howlerPluginStore from 'plugins/store';
import { useMemo, type ReactElement } from 'react';
import { usePluginStore } from 'react-pluggable';
import ActionButton from '../ActionButton';
import JSONViewer from '../json/JSONViewer';

export interface HowlerHelper {
  keyword: string;
  documentation?: {
    en: string;
    fr: string;
  };
  async?: boolean;
  hint?: string;
  callback?: Handlebars.HelperDelegate;
  componentCallback?: (...args: any[]) => ReactElement | Promise<ReactElement>;
}

interface Cell {
  column: string;
  row: string;
  value: string;
}

export class HowlerHelperError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'HowlerHelperError';
  }
}

const FETCH_RESULTS: { [url: string]: Promise<any> } = {};

export const useHelpers = (opts = { async: true, components: true }): HowlerHelper[] => {
  const pluginStore = usePluginStore();

  const allHelpers = useMemo(
    (): HowlerHelper[] =>
      [
        {
          keyword: 'equals',
          documentation: {
            en: 'Checks the equality of the string representation of the two arguments.',
            fr: "Vérifie l'égalité de la représentation en chaîne de caractères des deux arguments."
          },
          callback: (...args) => {
            args.pop(); // remove options
            const [arg1, arg2] = args;

            if (isNil(arg1) || isNil(arg2)) {
              throw new HowlerHelperError('Both arguments must be provided.');
            }
            return arg1.toString() === arg2.toString();
          },
          hint: 'Usage: {{equals arg1 arg2}}'
        },
        {
          keyword: 'and',
          documentation: {
            en: 'Runs the comparison `arg1 && arg2`, and returns the result.',
            fr: 'Exécute la comparaison `arg1 && arg2`, et retourne le résultat.'
          },
          callback: (...args) => {
            args.pop(); // remove options
            const [arg1, arg2] = args;

            return arg1 && arg2;
          },
          hint: 'Usage: {{and arg1 arg2}}'
        },
        {
          keyword: 'or',
          documentation: {
            en: 'Runs the comparison `arg1 || arg2`, and returns the result.',
            fr: 'Exécute la comparaison `arg1 || arg2`, et retourne le résultat.'
          },
          callback: (...args) => {
            args.pop(); // remove options
            const [arg1, arg2] = args;

            return arg1 || arg2;
          },
          hint: 'Usage: {{or arg1 arg2}}'
        },
        {
          keyword: 'not',
          documentation: {
            en: 'Runs the comparison `!arg`, and returns the result.',
            fr: 'Exécute la comparaison `!arg`, et retourne le résultat.'
          },
          callback: (...args) => {
            args.pop(); // remove options
            const arg = args[0];

            return !arg;
          },
          hint: 'Usage: {{not arg}}'
        },
        {
          keyword: 'curly',
          documentation: {
            en: 'Wraps the given argument in curly braces.',
            fr: "Entoure l'argument donné d'accolades."
          },
          callback: (...args) => {
            args.pop(); // remove options
            const arg1 = args[0];

            return new Handlebars.SafeString(`{{${arg1}}}`);
          },
          hint: 'Usage: {{curly arg}}'
        },
        {
          keyword: 'join',
          documentation: {
            en: 'Joins two string arguments with a given string `sep`, or the empty string as a default.',
            fr: 'Joint deux arguments de chaîne avec une chaîne donnée `sep`, ou la chaîne vide par défaut.'
          },
          callback: (...args) => {
            const context = args.pop();
            const [arg1, arg2] = args;

            return [arg1?.toString() ?? '', arg2?.toString() ?? ''].join(context.hash?.sep ?? '');
          },
          hint: 'Usage: {{join arg1 arg2 sep=string}}'
        },
        {
          keyword: 'upper',
          documentation: {
            en: 'Returns the uppercase representation of a string argument.',
            fr: "Retourne la représentation en majuscules d'un argument de chaîne."
          },
          callback: (...args) => {
            args.pop(); // remove options
            const val = args[0];

            if (isNil(val)) {
              throw new HowlerHelperError('Upper expects a string argument');
            }
            return val.toString().toLocaleUpperCase();
          },
          hint: 'Usage: {{upper val}}'
        },
        {
          keyword: 'lower',
          documentation: {
            en: 'Returns the lowercase representation of a string argument.',
            fr: "Retourne la représentation en minuscules d'un argument de chaîne."
          },
          callback: (...args) => {
            args.pop(); // remove options
            const val = args[0];

            if (isNil(val)) {
              throw new HowlerHelperError('Lower expects a string argument');
            }
            return val.toString().toLocaleLowerCase();
          },
          hint: 'Usage: {{lower val}}'
        },
        {
          keyword: 'fetch',
          documentation: {
            en: 'Fetches the url provided and returns the given (flattened) key from the returned JSON object. Note that the result must be JSON!',
            fr: "Récupère l'URL fournie et retourne la clé donnée (aplatie) de l'objet JSON retourné. Notez que le résultat doit être du JSON !"
          },
          async: true,
          callback: async (...args) => {
            args.pop(); // remove options
            const [url, key] = args;

            try {
              if (!FETCH_RESULTS[url]) {
                FETCH_RESULTS[url] = fetch(url).then(res => res.json());
              }

              const json = await FETCH_RESULTS[url];

              return flatten(json)[key];
            } catch {
              return '';
            }
          },
          hint: 'Usage: {{fetch url key}}'
        },
        {
          keyword: 'howler',
          documentation: {
            en: 'Given a howler hit ID, this helper renders a hit card for that ID.',
            fr: 'Étant donné un ID de résultat howler, cet assistant affiche une carte de résultat pour cet ID.'
          },
          componentCallback: (...args) => {
            args.pop(); // remove options
            const id = args[0];

            if (!id) {
              return <AppListEmpty />;
            }

            return <HitCard id={id} layout={HitLayout.NORMAL} />;
          },
          hint: 'Usage: {{howler hitId}}'
        },
        {
          keyword: 'entries',
          documentation: {
            en: 'Given a dict, return an array of {key, value} objects.',
            fr: "Étant donné un dictionnaire, retourne un tableau d'objets {key, value}."
          },
          callback: (...args) => {
            args.pop(); // remove options
            const obj = args[0];

            if (!isObject(obj)) {
              return new Handlebars.SafeString('Invalid Object.');
            }

            return Object.entries(obj).map(([key, value]) => ({ key, value }));
          },
          hint: 'Usage: {{entries obj}}'
        },
        {
          keyword: 'render_json',
          documentation: {
            en: 'Given JSON data, this helper renders a JSON viewer component.',
            fr: 'Étant donné des données JSON, cet assistant affiche un composant de visualisation JSON.'
          },
          componentCallback: (...args) => {
            args.pop(); // remove options
            const data = args[0];

            if (!data) {
              return <AppListEmpty />;
            }

            return <JSONViewer data={data} />;
          },
          hint: 'Usage: {{render_json obj}}'
        },
        {
          keyword: 'to_json',
          documentation: {
            en: 'Convert any object into a JSON string.',
            fr: "Convertit n'importe quel objet en chaîne JSON."
          },
          callback: (...args) => {
            args.pop(); // remove options
            const obj = args[0];

            return new Handlebars.SafeString(JSON.stringify(obj));
          },
          hint: 'Usage: {{to_json obj}}'
        },
        {
          keyword: 'parse_json',
          documentation: {
            en: 'Convert a JSON string into an object.',
            fr: 'Convertit une chaîne JSON en objet.'
          },
          callback: (...args) => {
            args.pop(); // remove options
            const str = args[0];

            if (isNil(str)) {
              throw new HowlerHelperError('Parse JSON expects a string argument');
            }
            try {
              return JSON.parse(str);
            } catch {
              throw new HowlerHelperError('Invalid JSON string');
            }
          },
          hint: 'Usage: {{parse_json str}}'
        },
        {
          keyword: 'get',
          documentation: {
            en: 'Returns the given (flattened) key from the provided object.',
            fr: "Retourne la clé donnée (aplatie) de l'objet fourni."
          },
          callback: (...args) => {
            args.pop(); // remove options
            const [data, key] = args;

            try {
              return get(data, key);
            } catch {
              return '';
            }
          },
          hint: 'Usage: {{get obj key}}'
        },
        {
          keyword: 'includes',
          documentation: {
            en: 'Checks if field is in string',
            fr: 'Vérifie si le champ est dans la chaîne'
          },
          callback: (...args) => {
            args.pop(); // remove options
            const [arg1, arg2] = args;

            return !!arg2 && !!arg1?.includes(arg2);
          },
          hint: 'Usage: {{includes str substr}}'
        },

        {
          keyword: 'table',
          documentation: {
            en: 'Render a table in markdown given an array of cells',
            fr: "Affiche un tableau en markdown à partir d'un tableau de cellules"
          },
          componentCallback: (...args) => {
            args.pop(); // remove options
            const cells: Cell[] = args[0];

            const columns = Object.keys(groupBy(cells, 'column'));
            const rows = groupBy(cells, 'row');

            return (
              <Paper sx={{ width: '95%', overflowX: 'auto', m: 1 }}>
                <Table>
                  <TableHead>
                    <TableRow>
                      {columns.map(col => (
                        <TableCell key={col} sx={{ maxWidth: '150px' }}>
                          {col
                            .split(/[_-]/)
                            .map(word => capitalize(word))
                            .join(' ')}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody sx={{ '& td': { wordBreak: 'break-word' } }}>
                    {Object.entries(rows).map(([rowId, _cells]) => {
                      return (
                        <TableRow key={rowId}>
                          {columns.map(col => {
                            const cell = _cells.find(row => row.column === col);

                            return <TableCell key={col + cell?.value}>{cell?.value ?? 'N/A'}</TableCell>;
                          })}
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </Paper>
            );
          },
          hint: 'Usage: {{table cells}}'
        },

        {
          keyword: 'action',
          documentation: {
            en: 'Execute a howler action given a specific action ID (from the URL when viewing the action, i.e. yaIKVqiKhWpyCsWdqsE4D)',
            fr: "Exécute une action howler à partir d'un ID d'action spécifique (de l'URL lors de la visualisation de l'action, par ex. yaIKVqiKhWpyCsWdqsE4D)"
          },
          componentCallback: (...args) => {
            const context = args.pop(); // remove options
            const [actionId, hitId] = args;

            return <ActionButton actionId={actionId} hitId={hitId} {...(context.hash ?? {})} />;
          },
          hint: 'Usage: {{action actionId hitId}}'
        },

        {
          keyword: 'replace',
          documentation: {
            en: '',
            fr: ''
          },
          callback: (...args) => {
            args.pop(); // remove options
            const [str, searchValue, replaceValue] = args;

            if (isNil(str) || isNil(searchValue) || isNil(replaceValue)) {
              throw new HowlerHelperError('Replace expects three arguments');
            }
            return str.toString().replaceAll(searchValue ?? '', replaceValue ?? '');
          },
          hint: 'Usage: {{replace str searchValue replaceValue}}'
        },

        ...howlerPluginStore.plugins.flatMap(plugin => pluginStore.executeFunction(`${plugin}.helpers`) as HowlerHelper)
      ].filter((entry: HowlerHelper) => (opts.async || !entry.async) && (opts.components || !entry.componentCallback)),
    [opts.async, opts.components, pluginStore]
  );

  return allHelpers;
};
