import { removeEmpty, searchObject } from 'utils/utils';

onmessage = (e: MessageEvent<[any, boolean, string, boolean]>) => {
  const [data, compact, query, flat] = e.data;

  const filteredData = removeEmpty(data, compact);

  const searchedData = searchObject(filteredData, query, flat);

  postMessage([searchedData]);
};
