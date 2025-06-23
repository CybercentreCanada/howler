const isDark = JSON.parse(localStorage.getItem('templateui.core.darkMode') || 'false');

if (isDark) {
  document.body.style.backgroundColor = '#121212';
} else {
  document.body.style.backgroundColor = '#fff';
}

window.addEventListener('load', () => {
  const observer = new MutationObserver(_mutations => {
    if (document.querySelector('#root').childElementCount > 0) {
      document.body.style.backgroundColor = '';
      observer.disconnect();
    }
  });

  observer.observe(document.body, { childList: true, subtree: true, attributes: false, characterData: false });
});
