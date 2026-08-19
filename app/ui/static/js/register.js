"use strict";

if (isLoggedIn()) {
  location.replace(page("dashboard"));
}

document
  .getElementById("register-form")
  .addEventListener("submit", async function (event) {
    event.preventDefault();
    var payload = {
      organization_name: document.getElementById("org-name").value.trim(),
      full_name: document.getElementById("full-name").value.trim(),
      email: document.getElementById("email").value.trim(),
      password: document.getElementById("password").value,
    };
    if (!payload.organization_name || !payload.full_name || !payload.email || !payload.password) {
      toast("All fields are required", "error");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email)) {
      toast("Enter a valid email address", "error");
      return;
    }
    if (payload.password.length < 8) {
      toast("Password must be at least 8 characters", "error");
      return;
    }
    var btn = this.querySelector("button[type=submit]");
    btn.disabled = true;
    try {
      var data = await api("/auth/register", {
        method: "POST",
        body: payload,
      });
      setToken(data.access_token);
      toast("Organization created. Welcome!", "success");
      location.href = page("dashboard");
    } catch (err) {
      toast(err.message, "error");
      btn.disabled = false;
    }
  });
