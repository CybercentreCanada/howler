const getXSRFCookie = () => {
  if (document.cookie !== undefined) {
    const token = document.cookie.split('; ').find(row => row.startsWith('XSRF-TOKEN='));
    if (token) {
      return token.split('=')[1] ?? null;
    }
  }

  return null;
};

export default getXSRFCookie;
