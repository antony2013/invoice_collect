"use strict";

initShell("staff.xhtml", "Staff");

var editingId = null;

function content() {
  return document.getElementById("content");
}

async function loadStaff() {
  var box = content();
  box.innerHTML = '<div class="loading">Loading staff&hellip;</div>';
  try {
    var staff = await api("/staff");
    renderStaff(staff);
  } catch (err) {
    box.innerHTML = '<div class="empty">' + esc(err.message) + "</div>";
  }
}

function renderStaff(staff) {
  var html =
    '<div class="toolbar"><span class="spacer"></span>' +
    '<button class="btn primary" id="btn-new-staff">+ New staff</button></div>' +
    '<div class="card"><div class="table-wrap"><table class="data"><thead><tr>' +
    "<th>Name</th><th>Email</th><th>Role</th><th>Status</th>" +
    '<th class="num">Assigned invoices</th><th></th></tr></thead><tbody>';

  if (!staff.length) {
    html += '<tr><td colspan="6" class="empty">No staff yet.</td></tr>';
  } else {
    staff.forEach(function (u) {
      var active = u.is_active
        ? '<span class="dot on"></span>Active'
        : '<span class="dot off"></span>Inactive';
      html +=
        "<tr><td>" + esc(u.full_name) + "</td>" +
        "<td>" + esc(u.email) + "</td>" +
        '<td><span class="badge ' + u.role + '">' + u.role + "</span></td>" +
        "<td>" + active + "</td>" +
        '<td class="num">' + u.assigned_invoice_count + "</td>" +
        '<td><button class="btn small" data-edit="' + u.id + '">Edit</button></td></tr>';
    });
  }

  html += "</tbody></table></div></div>";
  content().innerHTML = html;

  document
    .getElementById("btn-new-staff")
    .addEventListener("click", function () {
      openModal();
    });
  document.querySelectorAll("[data-edit]").forEach(function (btn) {
    btn.addEventListener("click", function () { openModal(btn.getAttribute("data-edit")); });
  });
}

function openModal(id) {
  editingId = id || null;
  var modal = document.getElementById("staff-modal");
  var form = document.getElementById("staff-form");
  form.reset();
  document.getElementById("s-active-wrap").style.display = "none";
  document.getElementById("s-pass-label").classList.add("required");
  document.getElementById("s-pass").value = "";

  if (editingId) {
    document.getElementById("staff-modal-title").textContent = "Edit staff";
    document.getElementById("s-email-wrap").style.display = "none";
    document.getElementById("s-active-wrap").style.display = "block";
    document.getElementById("s-pass-label").textContent = "New password (leave blank to keep)";
    document.getElementById("s-pass-label").classList.remove("required");
    api("/staff/" + editingId)
      .then(function (u) {
        document.getElementById("s-name").value = u.full_name;
        document.getElementById("s-active").checked = u.is_active;
      })
      .catch(function (err) { toast(err.message, "error"); });
  } else {
    document.getElementById("staff-modal-title").textContent = "New staff member";
    document.getElementById("s-email-wrap").style.display = "block";
    document.getElementById("s-pass-label").textContent = "Password";
  }
  modal.classList.add("open");
}

function closeModal() {
  document.getElementById("staff-modal").classList.remove("open");
}

async function submitStaff(event) {
  event.preventDefault();
  var fullName = document.getElementById("s-name").value.trim();
  if (!fullName) {
    toast("Full name is required", "error");
    return;
  }
  var btn = event.target.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    if (editingId) {
      var payload = { full_name: fullName, is_active: document.getElementById("s-active").checked };
      var newPass = document.getElementById("s-pass").value;
      if (newPass) {
        if (newPass.length < 8) {
          toast("Password must be at least 8 characters", "error");
          btn.disabled = false;
          return;
        }
        payload.password = newPass;
      }
      await api("/staff/" + editingId, { method: "PATCH", body: payload });
      toast("Staff updated", "success");
    } else {
      var email = document.getElementById("s-email").value.trim();
      var password = document.getElementById("s-pass").value;
      if (!email || !password) {
        toast("Email and password are required", "error");
        btn.disabled = false;
        return;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        toast("Enter a valid email address", "error");
        btn.disabled = false;
        return;
      }
      if (password.length < 8) {
        toast("Password must be at least 8 characters", "error");
        btn.disabled = false;
        return;
      }
      await api("/staff", { method: "POST", body: { email: email, full_name: fullName, password: password } });
      toast("Staff created", "success");
    }
    closeModal();
    loadStaff();
  } catch (err) {
    toast(err.message, "error");
  }
  btn.disabled = false;
}

document.getElementById("s-cancel").addEventListener("click", closeModal);
document.getElementById("staff-form").addEventListener("submit", submitStaff);
document.getElementById("staff-modal").addEventListener("click", function (event) {
  if (event.target === this) closeModal();
});

loadStaff();
