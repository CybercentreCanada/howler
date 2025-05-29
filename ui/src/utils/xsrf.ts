const getXSRFCookie = () => {
  if (document.cookie !== undefined) {
    try {
      // eslint-disable-next-line prefer-destructuring
      return document.cookie
        .split('; ')
        .find(row => row.startsWith('XSRF-TOKEN'))
        .split('=')[1];
    } catch (ex) {
      // Ignore... we will return null
    }
  }

  return null;
};

export default getXSRFCookie;
