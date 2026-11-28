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

// Make the new static pages reachable from existing navbar placeholders.
// This keeps navigation consistent without changing the dashboard markup.
const navigationPages = {
  "Courses": "courses.html",
  "Study Groups": "study-groups.html",
  "Study Sessions": "study-sessions.html",
  "Resources": "resources.html",
};

document.querySelectorAll(".navbar [data-demo-feature]").forEach((button) => {
  const destination = navigationPages[button.dataset.demoFeature];
  if (destination) {
    const link = document.createElement("a");
    link.className = button.className;
    link.href = destination;
    link.textContent = button.textContent;
    button.replaceWith(link);
  }
});

document.querySelectorAll("[data-demo-feature]").forEach((button) => {
  button.addEventListener("click", () => {
    showDemoFeedback(`${button.dataset.demoFeature} is a demo placeholder. Nothing was submitted or saved.`);
  });
});

// Search, create, and share forms are UI previews. No values are read or saved.
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
