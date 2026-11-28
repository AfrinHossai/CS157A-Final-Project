"use strict";

// UI placeholders only. No API requests, authentication, or data storage.
const feedback = document.getElementById("demo-feedback");
const loginForm = document.getElementById("login-form");

function showDemoFeedback(message) {
  if (feedback) {
    feedback.textContent = message;
  }
}

if (loginForm) {
  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    // Browser validation handles required fields and email format.
    // Do not read, log, or store the entered credentials.
    loginForm.reset();
    showDemoFeedback("Login is a placeholder in this frontend preview. Use “View demo dashboard” to explore the sample layout.");
  });
}

document.querySelectorAll("[data-demo-feature]").forEach((button) => {
  button.addEventListener("click", () => {
    showDemoFeedback(`${button.dataset.demoFeature} is a placeholder for a future frontend page. This demo does not save changes.`);
  });
});

// Bootstrap's collapse component handles the responsive navigation menu.
