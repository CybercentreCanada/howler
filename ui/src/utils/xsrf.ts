import { notNil } from './utils';

const getXSRFCookie = () => {
  if (notNil(document.cookie)) {
    const token = document.cookie.split('; ').find(row => row.startsWith('XSRF-TOKEN='));
    if (token) {
      return token.split('=')[1] ?? null;
    }
  }

  return null;
};

export default getXSRFCookie;
