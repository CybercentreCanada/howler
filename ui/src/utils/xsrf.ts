const getXSRFCookie = () => {
  if (document.cookie !== undefined) {
    try {
      // oxlint-disable-next-line prefer-destructuring
      return document.cookie
        .split('; ')
        .find(row => row.startsWith('XSRF-TOKEN'))
        .split('=')[1];
    } catch {
      // Ignore... we will return null
    }
  }

  return null;
};

export default getXSRFCookie;
