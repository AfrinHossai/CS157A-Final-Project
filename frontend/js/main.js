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

// Demo registration validates input locally, without creating an account.
const registerForm = document.getElementById("register-form");

if (registerForm) {
  const password = document.getElementById("register-password");
  const confirmPassword = document.getElementById("register-confirm-password");

  function validatePasswordMatch() {
    confirmPassword.setCustomValidity(password.value === confirmPassword.value ? "" : "Passwords must match.");
  }

  // Recheck both fields so changing either password clears stale mismatch errors.
  password.addEventListener("input", validatePasswordMatch);
  confirmPassword.addEventListener("input", validatePasswordMatch);

  registerForm.addEventListener("submit", (event) => {
    event.preventDefault();
    validatePasswordMatch();
    if (!registerForm.reportValidity()) {
      return;
    }
    // Clear the sample details; no credentials are logged, sent, or stored.
    registerForm.reset();
    confirmPassword.setCustomValidity("");
    showDemoFeedback("Demo validation passed. No account was created and no information was sent or saved. Return to Login to continue the preview.");
  });
}

document.querySelectorAll("[data-demo-feature]").forEach((button) => {
  button.addEventListener("click", () => {
    showDemoFeedback(`${button.dataset.demoFeature} is a demo placeholder. Nothing was submitted or saved.`);
  });
});

// Search, create, share, and message forms are UI previews. No values are read or saved.
document.querySelectorAll("[data-demo-form]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = `${form.dataset.demoForm} is a demo placeholder. Nothing was submitted or saved; the sample lists are unchanged.`;
    const formFeedback = form.querySelector("[data-form-feedback]");
    if (formFeedback) {
      // Keep form feedback visible inside the open modal.
      formFeedback.textContent = message;
    } else {
      showDemoFeedback(message);
    }
  });
});

// Bootstrap's collapse component handles the responsive navigation menu.
