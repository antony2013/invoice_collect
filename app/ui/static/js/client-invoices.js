"use strict";

initShell("client-invoices.xhtml", "My Invoices");

var STATUSES = ["PENDING", "PROCESSING", "COMPLETED", "REVIEW", "CANCELLED"];

var state = { status: "" };

async function loadInvoices() {
  var content = document.getElementById("content");
  content.innerHTML = '<div class="loading">Loading invoices&hellip;</div>';
  try {
    var me = await getCurrentUser();
    if (me.role !== "CLIENT") {
      content.innerHTML = '<div class="empty">Access denied.</div>';
      return;
    }
    var params = {};
    if (state.status) params.status = state.status;
    var data = await api("/clients/me/invoices" + qs(params));
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
      return '<option value="' + s + '"' + (s === state.status ? ' selected="selected"' : "") + ">" + s + "</option>";
    }).join("") +
    "</select>" +
    '<span class="spacer"></span>' +
    '<a class="btn primary" href="' + page("client-dashboard") + '">+ Upload invoice</a>' +
    "</div>";

  var rows = invoices
    .map(function (inv) {
      return (
        "<tr>" +
        '<td class="mono"><a href="' + page("client-invoice-detail") + "?id=" + inv.id + '">' +
        esc(inv.invoice_number) + "</a></td>" +
        "<td>" + fmtDate(inv.invoice_date) + "</td>" +
        "<td>" + statusBadge(inv.status) + "</td>" +
        '<td class="num">' + fmtMoney(inv.total_amount, inv.currency) + "</td>" +
        "<td>" + fmtDateTime(inv.created_at) + "</td>" +
        "</tr>"
      );
    })
    .join("");

  var table =
    '<div class="card"><div class="table-wrap"><table class="data">' +
    "<thead><tr><th>Number</th><th>Date</th><th>Status</th>" +
    '<th class="num">Total</th><th>Submitted</th></tr></thead>' +
    "<tbody>" +
    (rows || '<tr><td colspan="5" class="empty">No invoices yet. Upload your first invoice.</td></tr>') +
    "</tbody></table></div></div>";

  content.innerHTML = html + table;
  document.getElementById("filter-status").addEventListener("change", function () {
    state.status = this.value;
    loadInvoices();
  });
}

loadInvoices();
