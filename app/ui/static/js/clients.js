"use strict";

initShell("clients.xhtml", "Clients");

var editingId = null;

function isOwner() {
  return window.CURRENT_USER && window.CURRENT_USER.role === "OWNER";
}

function content() {
  return document.getElementById("content");
}

async function loadClients() {
  var box = content();
  box.innerHTML = '<div class="loading">Loading clients&hellip;</div>';
  try {
    var clients = await api("/clients");
    renderClients(clients);
  } catch (err) {
    box.innerHTML = '<div class="empty">' + esc(err.message) + "</div>";
  }
}

function renderClients(clients) {
  var html =
    '<div class="toolbar"><span class="spacer"></span>' +
    '<button class="btn primary" id="btn-new-client">+ New client</button></div>' +
    '<div class="card"><div class="table-wrap"><table class="data"><thead><tr>' +
    "<th>Name</th><th>Email</th><th>Phone</th><th class=\"num\">Invoices</th>" +
    '<th class="num">Total billed</th><th>Status</th><th>Account</th><th></th></tr></thead><tbody>';

  if (!clients.length) {
    html += '<tr><td colspan="8" class="empty">No clients yet. Create your first client.</td></tr>';
  } else {
    clients.forEach(function (c) {
      var active = c.is_active
        ? '<span class="dot on"></span>Active'
        : '<span class="dot off"></span>Inactive';
      var accountCell = c.account_email
        ? esc(c.account_email) +
          ' <button class="btn small" data-reset="' + c.id + '" data-name="' + esc(c.name) + '">Reset password</button>'
        : '<button class="btn small primary" data-invite="' + c.id + '" data-name="' + esc(c.name) + '">Invite</button>';
      html +=
        "<tr><td>" + esc(c.name) + "</td>" +
        "<td>" + esc(c.email || "-") + "</td>" +
        "<td>" + esc(c.phone || "-") + "</td>" +
        '<td class="num">' + c.invoice_count + "</td>" +
        '<td class="num">' + fmtMoney(c.total_billed) + "</td>" +
        "<td>" + active + "</td>" +
        "<td>" + accountCell + "</td>" +
        "<td>" +
        '<button class="btn small" data-edit="' + c.id + '">Edit</button> ' +
        (isOwner()
          ? '<button class="btn small danger" data-del="' + c.id + '">Delete</button>'
          : "") +
        "</td></tr>";
    });
  }

  html += "</tbody></table></div></div>";
  content().innerHTML = html;

  document
    .getElementById("btn-new-client")
    .addEventListener("click", function () {
      openModal();
    });

  document.querySelectorAll("[data-edit]").forEach(function (btn) {
    btn.addEventListener("click", function () { openModal(btn.getAttribute("data-edit")); });
  });
  document.querySelectorAll("[data-del]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      var id = btn.getAttribute("data-del");
      if (!window.confirm("Delete this client and all its invoices?")) return;
      try {
        await api("/clients/" + id, { method: "DELETE" });
        toast("Client deleted", "success");
        loadClients();
      } catch (err) {
        toast(err.message, "error");
      }
    });
  });
  document.querySelectorAll("[data-invite]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      openInviteModal(btn.getAttribute("data-invite"), btn.getAttribute("data-name"), false);
    });
  });
  document.querySelectorAll("[data-reset]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      openInviteModal(btn.getAttribute("data-reset"), btn.getAttribute("data-name"), true);
    });
  });
}

function openModal(id) {
  editingId = id || null;
  var modal = document.getElementById("client-modal");
  var form = document.getElementById("client-form");
  form.reset();
  document.getElementById("c-active-wrap").style.display = "none";
  document.getElementById("client-modal-title").textContent = "New client";

  if (editingId) {
    document.getElementById("client-modal-title").textContent = "Edit client";
    document.getElementById("c-active-wrap").style.display = "block";
    api("/clients/" + editingId)
      .then(function (c) {
        document.getElementById("c-name").value = c.name;
        document.getElementById("c-email").value = c.email || "";
        document.getElementById("c-phone").value = c.phone || "";
        document.getElementById("c-address").value = c.address || "";
        document.getElementById("c-notes").value = c.notes || "";
        document.getElementById("c-active").checked = c.is_active;
      })
      .catch(function (err) { toast(err.message, "error"); });
  }
  modal.classList.add("open");
}

function closeModal() {
  document.getElementById("client-modal").classList.remove("open");
}

async function submitClient(event) {
  event.preventDefault();
  var payload = {
    name: document.getElementById("c-name").value.trim(),
    email: document.getElementById("c-email").value.trim() || null,
    phone: document.getElementById("c-phone").value.trim() || null,
    address: document.getElementById("c-address").value.trim() || null,
    notes: document.getElementById("c-notes").value.trim() || null,
  };
  if (!payload.name) {
    toast("Name is required", "error");
    return;
  }
  if (payload.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email)) {
    toast("Enter a valid email address", "error");
    return;
  }
  if (editingId) payload.is_active = document.getElementById("c-active").checked;

  var btn = event.target.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    if (editingId) {
      await api("/clients/" + editingId, { method: "PATCH", body: payload });
      toast("Client updated", "success");
    } else {
      await api("/clients", { method: "POST", body: payload });
      toast("Client created", "success");
    }
    closeModal();
    loadClients();
  } catch (err) {
    toast(err.message, "error");
  }
  btn.disabled = false;
}

document.getElementById("c-cancel").addEventListener("click", closeModal);
document.getElementById("client-form").addEventListener("submit", submitClient);
document.getElementById("client-modal").addEventListener("click", function (event) {
  if (event.target === this) closeModal();
});

/* ---------------- invite / reset password ---------------- */

var inviteClientId = null;

function openInviteModal(clientId, name, resetMode) {
  inviteClientId = clientId;
  var modal = document.getElementById("invite-modal");
  document.getElementById("invite-client-name").value = name || "";
  var emailRow = document.getElementById("invite-email").closest(".field");
  emailRow.style.display = resetMode ? "none" : "";
  document.getElementById("invite-modal-title").textContent = resetMode
    ? "Reset client password"
    : "Invite client";
  document.getElementById("invite-password").placeholder = resetMode
    ? "New password"
    : "Initial password";
  var submitBtn = modal.querySelector("button[type=submit]");
  submitBtn.textContent = resetMode ? "Reset password" : "Invite client";
  document.getElementById("invite-form").reset();
  document.getElementById("invite-client-name").value = name || "";
  modal.classList.add("open");
  document.getElementById("invite-password").focus();
}

function closeInviteModal() {
  document.getElementById("invite-modal").classList.remove("open");
}

async function submitInvite(event) {
  event.preventDefault();
  var email = document.getElementById("invite-email").value.trim();
  var password = document.getElementById("invite-password").value;
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    toast("Enter a valid email address", "error");
    return;
  }
  if (password.length < 8) {
    toast("Password must be at least 8 characters", "error");
    return;
  }
  var btn = event.target.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    if (document.getElementById("invite-modal-title").textContent === "Reset client password") {
      await api("/clients/" + inviteClientId + "/invite", {
        method: "PATCH",
        body: { password: password },
      });
      toast("Password reset", "success");
    } else {
      await api("/clients/" + inviteClientId + "/invite", {
        method: "POST",
        body: { email: email, password: password },
      });
      toast("Client invited", "success");
    }
    closeInviteModal();
    loadClients();
  } catch (err) {
    toast(err.message, "error");
  }
  btn.disabled = false;
}

document.getElementById("invite-cancel").addEventListener("click", closeInviteModal);
document.getElementById("invite-form").addEventListener("submit", submitInvite);
document.getElementById("invite-modal").addEventListener("click", function (event) {
  if (event.target === this) closeInviteModal();
});

loadClients();
