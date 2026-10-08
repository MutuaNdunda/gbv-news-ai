document.addEventListener('submit', (event) => {
  if (!event.target.matches('.collection-stop')) return;
  if (!window.confirm('Stop this run gracefully? Completed work will be preserved.')) {
    event.preventDefault();
    return;
  }
  const button = event.target.querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = 'Requesting stop…';
});
