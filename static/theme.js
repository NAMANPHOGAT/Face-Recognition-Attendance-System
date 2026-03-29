(function () {
  const storageKey = 'theme_mode';
  const root = document.documentElement;
  const button = document.getElementById('themeToggle');

  function apply(theme) {
    root.setAttribute('data-theme', theme);
    if (button) button.textContent = theme === 'dark' ? '☀️ Light' : '🌙 Dark';
  }

  const saved = localStorage.getItem(storageKey);
  const initial = saved === 'dark' || saved === 'light' ? saved : 'light';
  apply(initial);

  if (button) {
    button.addEventListener('click', function () {
      const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      localStorage.setItem(storageKey, next);
      apply(next);
    });
  }
})();
