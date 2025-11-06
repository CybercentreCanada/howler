/* eslint-disable no-console */
import { Paper, Table, TableBody, TableCell, TableHead, TableRow } from '@mui/material';
import AppListEmpty from 'commons/components/display/AppListEmpty';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import { flatten } from 'flat';
import Handlebars from 'handlebars';
import { capitalize, get, groupBy, isObject } from 'lodash-es';
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
  callback?: Handlebars.HelperDelegate;
  componentCallback?: (...args: any[]) => ReactElement | Promise<ReactElement>;
}

interface Cell {
  column: string;
  row: string;
  value: string;
}

const FETCH_RESULTS: { [url: string]: Promise<any> } = {};

export const useHelpers = (): HowlerHelper[] => {
  const pluginStore = usePluginStore();

  const allHelpers = useMemo(
    (): HowlerHelper[] => [
      {
        keyword: 'equals',
        documentation: {
          en: 'Checks the equality of the string representation of the two arguments.',
          fr: "Vérifie l'égalité de la représentation en chaîne de caractères des deux arguments."
        },
        callback: (arg1, arg2) => arg1?.toString() === arg2.toString()
      },
      {
        keyword: 'and',
        documentation: {
          en: 'Runs the comparison `arg1 && arg2`, and returns the result.',
          fr: 'Exécute la comparaison `arg1 && arg2`, et retourne le résultat.'
        },
        callback: (arg1, arg2) => arg1 && arg2
      },
      {
        keyword: 'or',
        documentation: {
          en: 'Runs the comparison `arg1 || arg2`, and returns the result.',
          fr: 'Exécute la comparaison `arg1 || arg2`, et retourne le résultat.'
        },
        callback: (arg1, arg2) => arg1 || arg2
      },
      {
        keyword: 'not',
        documentation: {
          en: 'Runs the comparison `!arg`, and returns the result.',
          fr: 'Exécute la comparaison `!arg`, et retourne le résultat.'
        },
        callback: arg => !arg
      },
      {
        keyword: 'curly',
        documentation: {
          en: 'Wraps the given argument in curly braces.',
          fr: "Entoure l'argument donné d'accolades."
        },
        callback: arg1 => new Handlebars.SafeString(`{{${arg1}}}`)
      },
      {
        keyword: 'join',
        documentation: {
          en: 'Joins two string arguments with a given string `sep`, or the empty string as a default.',
          fr: 'Joint deux arguments de chaîne avec une chaîne donnée `sep`, ou la chaîne vide par défaut.'
        },
        callback: (arg1: string, arg2: string, context) =>
          [arg1?.toString() ?? '', arg2?.toString() ?? ''].join(context.hash?.sep ?? '')
      },
      {
        keyword: 'upper',
        documentation: {
          en: 'Returns the uppercase representation of a string argument.',
          fr: "Retourne la représentation en majuscules d'un argument de chaîne."
        },
        callback: (val: string) => val.toLocaleUpperCase()
      },
      {
        keyword: 'lower',
        documentation: {
          en: 'Returns the lowercase representation of a string argument.',
          fr: "Retourne la représentation en minuscules d'un argument de chaîne."
        },
        callback: (val: string) => val.toLocaleLowerCase()
      },
      {
        keyword: 'fetch',
        documentation: {
          en: 'Fetches the url provided and returns the given (flattened) key from the returned JSON object. Note that the result must be JSON!',
          fr: "Récupère l'URL fournie et retourne la clé donnée (aplatie) de l'objet JSON retourné. Notez que le résultat doit être du JSON !"
        },
        callback: async (url, key) => {
          try {
            if (!FETCH_RESULTS[url]) {
              FETCH_RESULTS[url] = fetch(url).then(res => res.json());
            }

            const json = await FETCH_RESULTS[url];

            return flatten(json)[key];
          } catch (e) {
            return '';
          }
        }
      },
      {
        keyword: 'howler',
        documentation: {
          en: 'Given a howler hit ID, this helper renders a hit card for that ID.',
          fr: 'Étant donné un ID de résultat howler, cet assistant affiche une carte de résultat pour cet ID.'
        },
        componentCallback: id => {
          if (!id) {
            return <AppListEmpty />;
          }

          return <HitCard id={id} layout={HitLayout.NORMAL} />;
        }
      },
      {
        keyword: 'entries',
        documentation: {
          en: 'Given a dict, return an array of {key, value} objects.',
          fr: "Étant donné un dictionnaire, retourne un tableau d'objets {key, value}."
        },
        callback: obj => {
          if (!isObject(obj)) {
            return new Handlebars.SafeString('Invalid Object.');
          }

          return Object.entries(obj).map(([key, value]) => ({ key, value }));
        }
      },
      {
        keyword: 'render_json',
        documentation: {
          en: 'Given JSON data, this helper renders a JSON viewer component.',
          fr: 'Étant donné des données JSON, cet assistant affiche un composant de visualisation JSON.'
        },
        componentCallback: data => {
          if (!data) {
            return <AppListEmpty />;
          }

          return <JSONViewer data={data} />;
        }
      },
      {
        keyword: 'to_json',
        documentation: {
          en: 'Convert any object into a JSON string.',
          fr: "Convertit n'importe quel objet en chaîne JSON."
        },
        callback: obj => {
          return new Handlebars.SafeString(JSON.stringify(obj));
        }
      },
      {
        keyword: 'parse_json',
        documentation: {
          en: 'Convert a JSON string into an object.',
          fr: 'Convertit une chaîne JSON en objet.'
        },
        callback: str => {
          return JSON.parse(str);
        }
      },
      {
        keyword: 'get',
        documentation: {
          en: 'Returns the given (flattened) key from the provided object.',
          fr: "Retourne la clé donnée (aplatie) de l'objet fourni."
        },
        callback: async (data, key) => {
          try {
            return get(data, key);
          } catch (e) {
            return '';
          }
        }
      },
      {
        keyword: 'includes',
        documentation: {
          en: 'Checks if field is in string',
          fr: 'Vérifie si le champ est dans la chaîne'
        },
        callback: (arg1, arg2) => {
          return !!arg2 && !!arg1?.includes(arg2);
        }
      },

      {
        keyword: 'table',
        documentation: {
          en: 'Render a table in markdown given an array of cells',
          fr: "Affiche un tableau en markdown à partir d'un tableau de cellules"
        },
        componentCallback: (cells: Cell[]) => {
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
        }
      },

      {
        keyword: 'action',
        documentation: {
          en: 'Execute a howler action given a specific action ID (from the URL when viewing the action, i.e. yaIKVqiKhWpyCsWdqsE4D)',
          fr: "Exécute une action howler à partir d'un ID d'action spécifique (de l'URL lors de la visualisation de l'action, par ex. yaIKVqiKhWpyCsWdqsE4D)"
        },
        componentCallback: (actionId: string, hitId: string, context) => {
          if (!actionId || !hitId) {
            console.warn('Missing parameters for the action button.');
            return null;
          }

          return <ActionButton actionId={actionId} hitId={hitId} {...(context.hash ?? {})} />;
        }
      },

      ...howlerPluginStore.plugins.flatMap(plugin => pluginStore.executeFunction(`${plugin}.helpers`) as HowlerHelper)
    ],
    [pluginStore]
  );

  return allHelpers;
};
