"use strict";

initShell("invoices.xhtml", "Invoice");

var invoiceId = getParam("id");
var ALLOWED_TRANSITIONS = {
  PENDING: ["PROCESSING", "CANCELLED"],
  PROCESSING: ["COMPLETED", "REVIEW", "CANCELLED"],
  COMPLETED: ["REVIEW", "CANCELLED"],
  REVIEW: ["PROCESSING", "COMPLETED", "CANCELLED"],
  CANCELLED: [],
};
var current = null;

function statusOptions(currentStatus) {
  var opts = [currentStatus];
  (ALLOWED_TRANSITIONS[currentStatus] || []).forEach(function (s) {
    if (opts.indexOf(s) === -1) opts.push(s);
  });
  return opts;
}

function isOwner() {
  return window.CURRENT_USER && window.CURRENT_USER.role === "OWNER";
}

function content() {
  return document.getElementById("content");
}

/* ---------------- load & render ---------------- */

async function loadDetail() {
  var box = content();
  box.innerHTML = '<div class="loading">Loading invoice&hellip;</div>';
  try {
    await getCurrentUser();
    current = await api("/invoices/" + invoiceId);
    renderAll();
  } catch (err) {
    box.innerHTML = '<div class="empty">' + esc(err.message) + "</div>";
  }
}

function renderAll() {
  var inv = current;
  var html =
    '<div class="btn-row" style="margin-bottom: 14px;">' +
    '<a class="btn" href="' + page("invoices") + '">← All invoices</a>' +
    (isOwner()
      ? '<button class="btn danger" id="btn-del-inv">Delete invoice</button>'
      : "") +
    "</div>" +
    '<div class="card">' +
    '<div class="btn-row" style="justify-content: space-between;">' +
    '<div><h2 class="mono">' + esc(inv.invoice_number) + "</h2>" +
    '<span class="muted">Client: ' + esc(inv.client_name) + "</span></div>" +
    statusBadge(inv.status) +
    "</div>" +
    '<div class="legend" style="margin-top: 12px;">' +
    '<span class="li">Date: ' + fmtDate(inv.invoice_date) + "</span>" +
    '<span class="li">Currency: ' + esc(inv.currency) + "</span>" +
    '<span class="li">Assigned: ' + esc(inv.assigned_to_name || "Unassigned") + "</span>" +
    '<span class="li">Total: <strong>' + fmtMoney(inv.total_amount, inv.currency) + "</strong></span>" +
    "</div>" +
    (inv.notes ? '<p class="muted" style="margin-top: 10px;">' + esc(inv.notes) + "</p>" : "") +
    "</div>";

  html += '<div class="card"><h3>Line items</h3><div class="btn-row" style="margin-bottom: 10px;">' +
    '<button class="btn small" id="btn-edit-items">Edit items</button>' +
    '<button class="btn small primary" id="btn-save-items" style="display: none;">Save items</button>' +
    '<button class="btn small" id="btn-cancel-items" style="display: none;">Cancel</button>' +
    "</div><div class=\"table-wrap\"><table class=\"data\"><thead><tr>" +
    "<th>Description</th><th class=\"num\">Qty</th><th class=\"num\">Unit price</th><th class=\"num\">Amount</th>" +
    "</tr></thead><tbody id=\"items-body\"></tbody></table></div></div>";

  html += '<div class="card"><h3>Update invoice</h3><div class="form-grid">' +
    '<div class="field"><label for="meta-status">Status</label><select id="meta-status"></select></div>' +
    (isOwner()
      ? '<div class="field"><label for="meta-assign">Assigned to</label><select id="meta-assign"></select></div>'
      : "") +
    '<div class="field full"><label for="meta-notes">Notes</label><textarea id="meta-notes"></textarea></div>' +
    "</div><div class=\"btn-row\" style=\"margin-top: 12px;\">" +
    '<button class="btn primary" id="btn-save-meta">Save changes</button></div></div>';

  html += '<div class="card"><h3>Files</h3><div class="btn-row" style="margin-bottom: 10px;">' +
    '<button class="btn small" id="btn-upload">Upload file</button></div>' +
    '<div class="file-list" id="file-list"></div></div>';

  content().innerHTML = html;

  renderItemsRows(false);
  renderMeta();
  renderFiles();
  wireActions();
}

function renderItemsRows(editMode) {
  var body = document.getElementById("items-body");
  if (editMode) {
    if (!current.items.length) addEditableRow("", "1", "0");
    body.innerHTML = "";
    current.items.forEach(function (item) {
      addEditableRow(item.description, item.quantity, item.unit_price);
    });
    return;
  }
  var rows = current.items
    .map(function (item) {
      return "<tr><td>" + esc(item.description) + "</td>" +
        '<td class="num">' + item.quantity + "</td>" +
        '<td class="num">' + fmtMoney(item.unit_price) + "</td>" +
        '<td class="num">' + fmtMoney(item.amount) + "</td></tr>";
    })
    .join("");
  body.innerHTML =
    rows || '<tr><td colspan="4" class="empty">No line items.</td></tr>';
}

function addEditableRow(desc, qty, price) {
  var body = document.getElementById("items-body");
  var row = document.createElement("tr");
  row.innerHTML =
    '<td><input class="e-desc" type="text" value="' + esc(desc) + '" /></td>' +
    '<td><input class="e-qty" type="number" min="0" step="0.01" value="' + esc(qty) + '" /></td>' +
    '<td><input class="e-price" type="number" min="0" step="0.01" value="' + esc(price) + '" /></td>' +
    '<td><button type="button" class="btn small danger">Remove</button></td>';
  row.querySelector("button").addEventListener("click", function () { row.remove(); });
  body.appendChild(row);
}

function renderMeta() {
  var statusSel = document.getElementById("meta-status");
  statusSel.innerHTML = statusOptions(current.status).map(function (s) {
    return '<option value="' + s + '"' + (s === current.status ? " selected=\"selected\"" : "") + ">" + s + "</option>";
  }).join("");
  document.getElementById("meta-notes").value = current.notes || "";

  var assignSel = document.getElementById("meta-assign");
  if (!assignSel) return;
  assignSel.innerHTML = '<option value="">Unassigned</option>';

  var me = window.CURRENT_USER;
  api("/staff").then(function (staff) {
    var opts = staff
      .filter(function (u) {
        return u.is_active;
      })
      .map(function (u) {
        return '<option value="' + u.id + '">' + esc(u.full_name) + "</option>";
      });
    opts.unshift('<option value="' + me.id + '">' + esc(me.full_name) + " (Owner)</option>");
    assignSel.insertAdjacentHTML("beforeend", opts.join(""));
    if (current.assigned_to_id) assignSel.value = current.assigned_to_id;
  });
}

function decodeFilename(disposition) {
  var m = /filename\*=UTF-8''([^;]+)/i.exec(disposition || "");
  if (m) {
    try {
      return decodeURIComponent(m[1]);
    } catch (e) {
      return m[1];
    }
  }
  return "download";
}

async function downloadFile(fileId) {
  var resp = await fetch(
    API_BASE + "/invoices/" + invoiceId + "/files/" + fileId + "/download",
    { headers: { Authorization: "Bearer " + getToken() } }
  );
  if (resp.status === 401) {
    clearToken();
    location.href = page("login");
    throw new Error("Session expired");
  }
  if (!resp.ok) {
    var detail = null;
    try {
      detail = (await resp.json()).detail;
    } catch (e) {
      detail = null;
    }
    throw new Error(detailMessage(detail));
  }
  var blob = await resp.blob();
  var url = URL.createObjectURL(blob);
  var a = document.createElement("a");
  a.href = url;
  a.download = decodeFilename(resp.headers.get("Content-Disposition"));
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(function () {
    URL.revokeObjectURL(url);
  }, 1000);
}

function renderFiles() {
  var list = document.getElementById("file-list");
  if (!current.files.length) {
    list.innerHTML = '<div class="empty">No files attached.</div>';
    return;
  }
  list.innerHTML = current.files
    .map(function (f) {
      return (
        '<div class="file-item">' +
        '<span class="fname">📄 ' + esc(f.original_name) + "</span>" +
        '<span class="fmeta">' + fmtBytes(f.size_bytes) + " · " + esc(f.uploaded_by_name || "-") + "</span>" +
        '<button class="btn small" data-dl="' + f.id + '">Download</button>' +
        '<button class="btn small danger" data-del-file="' + f.id + '">Delete</button>' +
        "</div>"
      );
    })
    .join("");
  document.querySelectorAll("[data-dl]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      var fileId = btn.getAttribute("data-dl");
      btn.disabled = true;
      btn.textContent = "Downloading…";
      try {
        await downloadFile(fileId);
      } catch (err) {
        toast(err.message, "error");
      }
      btn.textContent = "Download";
      btn.disabled = false;
    });
  });
  document.querySelectorAll("[data-del-file]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      if (!window.confirm("Delete this file?")) return;
      try {
        await api("/invoices/" + invoiceId + "/files/" + btn.getAttribute("data-del-file"), {
          method: "DELETE",
        });
        toast("File deleted", "success");
        loadDetail();
      } catch (err) {
        toast(err.message, "error");
      }
    });
  });
}

function wireActions() {
  document.getElementById("btn-edit-items").addEventListener("click", function () {
    renderItemsRows(true);
    document.getElementById("btn-edit-items").style.display = "none";
    document.getElementById("btn-save-items").style.display = "inline-flex";
    document.getElementById("btn-cancel-items").style.display = "inline-flex";
  });
  document.getElementById("btn-cancel-items").addEventListener("click", function () {
    renderItemsRows(false);
    document.getElementById("btn-edit-items").style.display = "inline-flex";
    document.getElementById("btn-save-items").style.display = "none";
    document.getElementById("btn-cancel-items").style.display = "none";
  });
  document.getElementById("btn-save-items").addEventListener("click", async function () {
    var items = [];
    document.querySelectorAll("#items-body tr").forEach(function (row) {
      var desc = row.querySelector(".e-desc").value.trim();
      if (!desc) return;
      items.push({
        description: desc,
        quantity: row.querySelector(".e-qty").value || "1",
        unit_price: row.querySelector(".e-price").value || "0",
      });
    });
    try {
      current = await api("/invoices/" + invoiceId, {
        method: "PATCH",
        body: { items: items },
      });
      toast("Items saved", "success");
      loadDetail();
    } catch (err) {
      toast(err.message, "error");
    }
  });

  document.getElementById("btn-save-meta").addEventListener("click", async function () {
    var payload = { status: document.getElementById("meta-status").value };
    var assign = document.getElementById("meta-assign");
    if (assign) {
      payload.assigned_to_id = assign.value || null;
    }
    var notes = document.getElementById("meta-notes").value.trim();
    payload.notes = notes || null;
    try {
      current = await api("/invoices/" + invoiceId, {
        method: "PATCH",
        body: payload,
      });
      toast("Invoice updated", "success");
      loadDetail();
    } catch (err) {
      toast(err.message, "error");
    }
  });

  document.getElementById("btn-upload").addEventListener("click", function () {
    document.getElementById("file-input").click();
  });
  document.getElementById("file-input").addEventListener("change", async function () {
    var file = this.files[0];
    if (!file) return;
    var fd = new FormData();
    fd.append("upload", file);
    try {
      await api("/invoices/" + invoiceId + "/files", { method: "POST", body: fd });
      toast("File uploaded", "success");
      this.value = "";
      loadDetail();
    } catch (err) {
      toast(err.message, "error");
      this.value = "";
    }
  });

  var delBtn = document.getElementById("btn-del-inv");
  if (delBtn) {
    delBtn.addEventListener("click", async function () {
      if (!window.confirm("Delete this invoice and all its files?")) return;
      try {
        await api("/invoices/" + invoiceId, { method: "DELETE" });
        toast("Invoice deleted", "success");
        location.href = page("invoices");
      } catch (err) {
        toast(err.message, "error");
      }
    });
  }
}

loadDetail();
