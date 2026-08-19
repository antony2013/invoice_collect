"use strict";

initShell("dashboard.xhtml", "Dashboard");

var STATUS_ORDER = ["PENDING", "PROCESSING", "COMPLETED", "REVIEW", "CANCELLED"];

async function loadDashboard() {
  var content = document.getElementById("content");
  content.innerHTML = '<div class="loading">Loading dashboard&hellip;</div>';
  try {
    var me = await getCurrentUser();
    if (me.role === "STAFF") {
      await renderStaffDashboard(content);
    } else {
      await renderOwnerDashboard(content);
    }
  } catch (err) {
    content.innerHTML = '<div class="empty">' + esc(err.message) + "</div>";
  }
}

async function renderOwnerDashboard(content) {
  var data = await api("/reports/summary?months=6&limit=5");
  renderStats(content, data);
  renderStatusRow(content, data.by_status);
  renderMonthly(content, data.monthly);
  renderTopClients(content, data.top_clients);
}

async function renderStaffDashboard(content) {
  var data = await api("/invoices?page_size=100");
  var invs = data.items;
  var counts = { PENDING: 0, PROCESSING: 0, COMPLETED: 0, REVIEW: 0, CANCELLED: 0 };
  invs.forEach(function (inv) {
    if (counts.hasOwnProperty(inv.status)) counts[inv.status] += 1;
  });

  content.innerHTML =
    '<div class="stats">' +
    '<div class="stat"><div class="label">My tasks</div><div class="value">' +
    invs.length +
    "</div></div>" +
    '<div class="stat"><div class="label">Pending</div><div class="value">' +
    counts.PENDING +
    "</div></div>" +
    '<div class="stat"><div class="label">In progress</div><div class="value">' +
    counts.PROCESSING +
    "</div></div>" +
    '<div class="stat"><div class="label">Completed</div><div class="value">' +
    counts.COMPLETED +
    "</div></div>" +
    "</div>";

  renderStatusRow(content, counts);

  var rows = invs
    .map(function (inv) {
      return (
        "<tr>" +
        '<td class="mono"><a href="' + page("invoice-detail") + "?id=" + inv.id + '">' +
        esc(inv.invoice_number) + "</a></td>" +
        "<td>" + esc(inv.client_name) + "</td>" +
        "<td>" + fmtDate(inv.invoice_date) + "</td>" +
        "<td>" + statusBadge(inv.status) + "</td>" +
        '<td class="num">' + fmtMoney(inv.total_amount, inv.currency) + "</td>" +
        "</tr>"
      );
    })
    .join("");
  content.insertAdjacentHTML(
    "beforeend",
    '<div class="card"><h3>My assigned invoices</h3>' +
      '<div class="table-wrap"><table class="data">' +
      "<thead><tr><th>Number</th><th>Client</th><th>Date</th><th>Status</th>" +
      '<th class="num">Total</th></tr></thead>' +
      "<tbody>" +
      (rows || '<tr><td colspan="5" class="empty">No invoices assigned to you.</td></tr>') +
      "</tbody></table></div></div>"
  );
}

function renderStats(content, data) {
  var html =
    '<div class="stats">' +
    '<div class="stat"><div class="label">Total invoices</div><div class="value">' +
    data.total_invoices +
    "</div></div>" +
    '<div class="stat"><div class="label">Total billed</div><div class="value">' +
    fmtMoney(data.total_billed) +
    "</div></div>" +
    '<div class="stat"><div class="label">Top clients</div><div class="value">' +
    data.top_clients.length +
    "</div></div>" +
    "</div>";
  content.innerHTML = html;
}

function renderStatusRow(content, byStatus) {
  var chips = STATUS_ORDER.map(function (status) {
    return (
      '<span class="badge ' + status + '">' + status + ": " + byStatus[status] +
      "</span>"
    );
  }).join(" ");
  content.insertAdjacentHTML(
    "beforeend",
    '<div class="card"><h3>Invoices by status</h3><div class="legend">' +
      chips +
      "</div></div>"
  );
}

function renderMonthly(content, monthly) {
  var rows = monthly
    .map(function (m) {
      return (
        "<tr><td>" + esc(m.year_month) + "</td>" +
        '<td class="num">' + m.count + "</td>" +
        '<td class="num">' + fmtMoney(m.amount) + "</td></tr>"
      );
    })
    .join("");
  content.insertAdjacentHTML(
    "beforeend",
    '<div class="card"><h3>Monthly billed (last 6 months)</h3>' +
      '<div class="table-wrap"><table class="data">' +
      "<thead><tr><th>Month</th><th class=\"num\">Invoices</th><th class=\"num\">Amount</th></tr></thead>" +
      "<tbody>" + rows + "</tbody></table></div></div>"
  );
}

function renderTopClients(content, clients) {
  if (!clients.length) {
    content.insertAdjacentHTML(
      "beforeend",
      '<div class="card"><h3>Top clients</h3><div class="empty">No invoices yet.</div></div>'
    );
    return;
  }
  var rows = clients
    .map(function (c) {
      return (
        "<tr><td>" + esc(c.client_name) + "</td>" +
        '<td class="num">' + c.invoice_count + "</td>" +
        '<td class="num">' + fmtMoney(c.total_amount) + "</td></tr>"
      );
    })
    .join("");
  content.insertAdjacentHTML(
    "beforeend",
    '<div class="card"><h3>Top clients by revenue</h3>' +
      '<div class="table-wrap"><table class="data">' +
      "<thead><tr><th>Client</th><th class=\"num\">Invoices</th><th class=\"num\">Total</th></tr></thead>" +
      "<tbody>" + rows + "</tbody></table></div></div>"
  );
}

loadDashboard();
