// Debounce helper for search (if needed when we add AJAX)
function debounce(fn, delay=300) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), delay);
  };
}