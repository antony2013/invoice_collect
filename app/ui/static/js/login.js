"use strict";

if (isLoggedIn()) {
  location.replace(page("dashboard"));
}

document
  .getElementById("login-form")
  .addEventListener("submit", async function (event) {
    event.preventDefault();
    var email = document.getElementById("email").value.trim();
    var password = document.getElementById("password").value;
    var btn = this.querySelector("button[type=submit]");
    btn.disabled = true;
    try {
      var data = await api("/auth/login", {
        method: "POST",
        body: { email: email, password: password },
      });
      setToken(data.access_token);
      var role = data.user && data.user.role;
      location.href = role === "CLIENT" ? page("client-dashboard") : page("dashboard");
    } catch (err) {
      toast(err.message, "error");
      btn.disabled = false;
    }
  });
