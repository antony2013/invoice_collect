"use strict";

initShell("invoices.xhtml", "Invoices");

var state = { page: 1, pageSize: 20, status: "", clientId: "", total: 0 };

var STATUSES = ["PENDING", "PROCESSING", "COMPLETED", "REVIEW", "CANCELLED"];

function isOwner() {
  return window.CURRENT_USER && window.CURRENT_USER.role === "OWNER";
}

/* ---------------- rendering ---------------- */

async function loadInvoices() {
  var content = document.getElementById("content");
  content.innerHTML = '<div class="loading">Loading invoices&hellip;</div>';
  try {
    await getCurrentUser();
    var params = { page: state.page, page_size: state.pageSize };
    if (state.status) params.status = state.status;
    if (state.clientId) params.client_id = state.clientId;
    var data = await api("/invoices" + qs(params));
    state.total = data.total;
    renderContent(content, data.items);
  } catch (err) {
    content.innerHTML = '<div class="empty">' + esc(err.message) + "</div>";
  }
}

function renderContent(content, invoices) {
  var html =
    '<div class="toolbar">' +
    '<select id="filter-status">' +
    '<option value="">All statuses</option>' +
    STATUSES.map(function (s) {
      return '<option value="' + s + '"' + (s === state.status ? " selected=\"selected\"" : "") + ">" + s + "</option>";
    }).join("") +
    "</select>" +
    (isOwner()
      ? '<select id="filter-client"><option value="">All clients</option></select>'
      : "") +
    '<span class="spacer"></span>' +
    (isOwner()
      ? '<button class="btn primary" id="btn-new">+ New invoice</button>'
      : "") +
    "</div>";

  var rows = invoices
    .map(function (inv) {
      return (
        "<tr>" +
        '<td class="mono"><a href="' + page("invoice-detail") + "?id=" + inv.id + '">' +
        esc(inv.invoice_number) + "</a></td>" +
        "<td>" + esc(inv.client_name) + "</td>" +
        "<td>" + fmtDate(inv.invoice_date) + "</td>" +
        "<td>" + statusBadge(inv.status) + "</td>" +
        '<td class="num">' + fmtMoney(inv.total_amount, inv.currency) + "</td>" +
        "<td>" + esc(inv.assigned_to_name || "-") + "</td>" +
        "<td>" +
        (isOwner()
          ? '<button class="btn small danger" data-del="' + inv.id + '">Delete</button>'
          : "") +
        "</td>" +
        "</tr>"
      );
    })
    .join("");

  var table =
    '<div class="card"><div class="table-wrap"><table class="data">' +
    "<thead><tr><th>Number</th><th>Client</th><th>Date</th><th>Status</th>" +
    '<th class="num">Total</th><th>Assigned</th><th></th></tr></thead>' +
    "<tbody>" + (rows || '<tr><td colspan="7" class="empty">No invoices found.</td></tr>') + "</tbody>" +
    "</table></div>" +
    renderPagination() +
    "</div>";

  content.innerHTML = html + table;

  wireToolbar();
  wireDeleteButtons();
}

function renderPagination() {
  var pages = Math.max(1, Math.ceil(state.total / state.pageSize));
  return (
    '<div class="pagination">' +
    '<span>' + (state.total === 0 ? "0" : (state.page - 1) * state.pageSize + 1) +
    "-" + Math.min(state.page * state.pageSize, state.total) + " of " + state.total + "</span>" +
    '<button class="btn small" id="pg-prev" ' + (state.page <= 1 ? "disabled=\"disabled\"" : "") + ">Previous</button>" +
    "<span>Page " + state.page + " / " + pages + "</span>" +
    '<button class="btn small" id="pg-next" ' + (state.page >= pages ? "disabled=\"disabled\"" : "") + ">Next</button>" +
    "</div>"
  );
}

function wireToolbar() {
  var statusSel = document.getElementById("filter-status");
  if (statusSel) {
    statusSel.addEventListener("change", function () {
      state.status = statusSel.value;
      state.page = 1;
      loadInvoices();
    });
  }

  var clientSel = document.getElementById("filter-client");
  if (clientSel) {
    clientSel.addEventListener("change", function () {
      state.clientId = clientSel.value;
      state.page = 1;
      loadInvoices();
    });
    api("/clients").then(function (clients) {
      clientSel.innerHTML =
        '<option value="">All clients</option>' +
        clients.map(function (c) { return '<option value="' + c.id + '">' + esc(c.name) + "</option>"; }).join("");
    });
  }

  var prev = document.getElementById("pg-prev");
  var next = document.getElementById("pg-next");
  if (prev) prev.addEventListener("click", function () { state.page -= 1; loadInvoices(); });
  if (next) next.addEventListener("click", function () { state.page += 1; loadInvoices(); });

  var btnNew = document.getElementById("btn-new");
  if (btnNew) btnNew.addEventListener("click", openCreateModal);
}

function wireDeleteButtons() {
  document.querySelectorAll("[data-del]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      var id = btn.getAttribute("data-del");
      if (!window.confirm("Delete this invoice permanently?")) return;
      try {
        await api("/invoices/" + id, { method: "DELETE" });
        toast("Invoice deleted", "success");
        loadInvoices();
      } catch (err) {
        toast(err.message, "error");
      }
    });
  });
}

/* ---------------- create modal ---------------- */

function openCreateModal() {
  var modal = document.getElementById("create-modal");
  document.getElementById("inv-client").innerHTML =
    '<option value="">Loading clients&hellip;</option>';
  document.getElementById("item-rows").innerHTML = "";
  addItemRow("", "1", "0");
  var today = new Date();
  document.getElementById("inv-date").value = today.toISOString().slice(0, 10);

  api("/clients").then(function (clients) {
    var sel = document.getElementById("inv-client");
    sel.innerHTML =
      '<option value="">Select client</option>' +
      clients.map(function (c) { return '<option value="' + c.id + '">' + esc(c.name) + "</option>"; }).join("");
  });

  modal.classList.add("open");
}

function closeCreateModal() {
  document.getElementById("create-modal").classList.remove("open");
}

function addItemRow(desc, qty, price) {
  var row = document.createElement("div");
  row.className = "item-row";
  row.innerHTML =
    '<input class="i-desc" type="text" placeholder="Description" value="' + esc(desc) + '" />' +
    '<input class="i-qty" type="number" min="0" step="0.01" value="' + esc(qty) + '" />' +
    '<input class="i-price" type="number" min="0" step="0.01" value="' + esc(price) + '" />' +
    '<span class="line-total">0.00</span>' +
    '<button type="button" class="btn small danger" title="Remove">×</button>';
  var total = row.querySelector(".line-total");
  var qtyIn = row.querySelector(".i-qty");
  var priceIn = row.querySelector(".i-price");
  function update() {
    var q = parseFloat(qtyIn.value) || 0;
    var p = parseFloat(priceIn.value) || 0;
    total.textContent = (q * p).toFixed(2);
  }
  qtyIn.addEventListener("input", update);
  priceIn.addEventListener("input", update);
  row.querySelector("button").addEventListener("click", function () {
    row.remove();
  });
  document.getElementById("item-rows").appendChild(row);
}

function collectItems() {
  var items = [];
  document.querySelectorAll("#item-rows .item-row").forEach(function (row) {
    var desc = row.querySelector(".i-desc").value.trim();
    var qty = row.querySelector(".i-qty").value;
    var price = row.querySelector(".i-price").value;
    if (!desc) return;
    items.push({
      description: desc,
      quantity: qty || "1",
      unit_price: price || "0",
    });
  });
  return items;
}

async function submitCreate(event) {
  event.preventDefault();
  var payload = {
    client_id: document.getElementById("inv-client").value,
    invoice_date: document.getElementById("inv-date").value,
    currency: (document.getElementById("inv-currency").value || "USD").toUpperCase(),
    items: collectItems(),
  };
  var number = document.getElementById("inv-number").value.trim();
  if (number) payload.invoice_number = number;
  var notes = document.getElementById("inv-notes").value.trim();
  if (notes) payload.notes = notes;
  if (!payload.client_id) {
    toast("Please select a client", "error");
    return;
  }
  if (!payload.invoice_date) {
    toast("Please choose an invoice date", "error");
    return;
  }
  var btn = event.target.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    var created = await api("/invoices", { method: "POST", body: payload });
    closeCreateModal();
    toast("Invoice " + created.invoice_number + " created", "success");
    location.href = page("invoice-detail") + "?id=" + created.id;
  } catch (err) {
    toast(err.message, "error");
    btn.disabled = false;
  }
}

document.getElementById("add-item").addEventListener("click", function () {
  addItemRow("", "1", "0");
});
document.getElementById("create-cancel").addEventListener("click", closeCreateModal);
document.getElementById("create-form").addEventListener("submit", submitCreate);
document.getElementById("create-modal").addEventListener("click", function (event) {
  if (event.target === this) closeCreateModal();
});

loadInvoices();
