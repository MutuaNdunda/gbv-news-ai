/* Private bodies are rendered as text; never put article HTML into the DOM. */
document.querySelectorAll('[data-performance-body]').forEach(button => {
  button.addEventListener('click', async () => {
    const output = button.nextElementSibling;
    if (!output.hidden) { output.hidden = true; return; }
    button.disabled = true;
    try {
      const response = await fetch(button.dataset.performanceBody, {cache: 'no-store', credentials: 'same-origin'});
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
        throw new Error('Access expired or comparison blocked. Reload and unlock the private workspace.');
      }
      const content = await response.json();
      output.textContent = content.article_text || content.content_issue || 'Verified body unavailable.';
    } catch (error) { output.textContent = error.message; }
    finally { output.hidden = false; button.disabled = false; }
  });
});
