const isDark = JSON.parse(localStorage.getItem('templateui.core.darkMode') || 'false');

document.body.style.backgroundColor = isDark ? '#121212' : '#fff';

window.addEventListener('load', () => {
  const observer = new MutationObserver(_mutations => {
    if (document.querySelector('#root').childElementCount > 0) {
      document.body.style.backgroundColor = '';
      observer.disconnect();
    }
  });

  observer.observe(document.body, { childList: true, subtree: true, attributes: false, characterData: false });
});
