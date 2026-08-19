"use strict";

initShell("organization.xhtml", "Organization");

var isOwnerUser =
  window.CURRENT_USER && window.CURRENT_USER.role === "OWNER";

function content() {
  return document.getElementById("content");
}

async function loadOrg() {
  var box = content();
  box.innerHTML = '<div class="loading">Loading organization&hellip;</div>';
  try {
    var org = await api("/organizations/me");
    renderOrg(org);
  } catch (err) {
    box.innerHTML = '<div class="empty">' + esc(err.message) + "</div>";
  }
}

function renderOrg(org) {
  var html =
    '<div class="card"><h3>Details</h3>' +
    '<div class="legend">' +
    '<span class="li">Name: <strong>' + esc(org.name) + "</strong></span>" +
    '<span class="li">Status: ' + (org.is_active ? "Active" : "Inactive") + "</span>" +
    '<span class="li">Created: ' + fmtDate(org.created_at) + "</span>" +
    "</div>" +
    '<div class="stats" style="margin-top: 14px;">' +
    '<div class="stat"><div class="label">Staff</div><div class="value">' + org.staff_count + "</div></div>" +
    '<div class="stat"><div class="label">Clients</div><div class="value">' + org.client_count + "</div></div>" +
    '<div class="stat"><div class="label">Invoices</div><div class="value">' + org.invoice_count + "</div></div>" +
    "</div></div>";

  html += '<div class="card"><h3>Rename organization</h3>' +
    '<form id="org-form" action="" method="post">' +
    '<div class="form-grid"><div class="field"><label class="required" for="org-name">Organization name</label>' +
    '<input id="org-name" type="text" value="' + esc(org.name) + '" /></div></div>' +
    '<div class="btn-row" style="margin-top: 12px;">' +
    '<button class="btn primary" type="submit">Save name</button></div>' +
    "</form></div>";

  content().innerHTML = html;

  if (!isOwnerUser) {
    var form = document.getElementById("org-form");
    form.querySelector("input").disabled = true;
    form.querySelector("button").disabled = true;
    var note = document.createElement("p");
    note.className = "muted";
    note.textContent = "Only the owner can rename the organization.";
    form.appendChild(note);
    return;
  }

  document.getElementById("org-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    var name = document.getElementById("org-name").value.trim();
    if (!name) {
      toast("Name is required", "error");
      return;
    }
    var btn = event.target.querySelector("button[type=submit]");
    btn.disabled = true;
    try {
      await api("/organizations/me", { method: "PATCH", body: { name: name } });
      toast("Organization renamed", "success");
      loadOrg();
    } catch (err) {
      toast(err.message, "error");
      btn.disabled = false;
    }
  });
}

loadOrg();
