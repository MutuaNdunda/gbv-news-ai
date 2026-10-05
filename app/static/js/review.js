/* Convenience only: the backend validates every decision and label. */
const reviewForm = document.getElementById('human-review-form');
if (reviewForm) {
  const decision = document.getElementById('decision');
  const label = document.getElementById('human_label');
  const category = document.getElementById('error_category');
  const reason = document.getElementById('reason');
  const update = () => {
    const confirming = decision.value === 'confirmed';
    const correcting = decision.value === 'corrected';
    if (confirming) label.value = reviewForm.dataset.machineLabel;
    if (!confirming && !correcting) label.value = '';
    label.disabled = !correcting;
    label.required = correcting;
    category.required = correcting;
    reason.required = correcting;
  };
  decision.addEventListener('change', update);
  update();
}
