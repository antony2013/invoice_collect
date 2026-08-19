"use strict";

initShell("client-dashboard.xhtml", "Client Dashboard");

var STATUS_ORDER = ["PENDING", "PROCESSING", "COMPLETED", "REVIEW", "CANCELLED"];

async function loadClientDashboard() {
  var content = document.getElementById("content");
  content.innerHTML = '<div class="loading">Loading dashboard&hellip;</div>';
  try {
    var me = await getCurrentUser();
    if (me.role !== "CLIENT") {
      content.innerHTML = '<div class="empty">Access denied.</div>';
      return;
    }
    var data = await api("/clients/me/invoices?page_size=100");
    renderUploadCard(content, data.items);
    renderStatusRow(content, data.items);
    renderRecent(content, data.items);
  } catch (err) {
    content.innerHTML = '<div class="empty">' + esc(err.message) + "</div>";
  }
}

function renderUploadCard(content, invoices) {
  content.innerHTML =
    '<div class="card">' +
    '<h3>Upload an invoice</h3>' +
    '<p class="muted">Choose an invoice file to submit it for processing.</p>' +
    '<div class="form-grid">' +
    '<div class="field full">' +
    '<input type="file" id="up-file" accept=".pdf,.png,.jpg,.jpeg,.webp,.txt" />' +
    "</div>" +
    '<div class="field full">' +
    '<textarea id="up-notes" placeholder="Optional notes for the processing team"></textarea>' +
    "</div>" +
    "</div>" +
    '<button class="btn primary" id="up-submit">Upload invoice</button>' +
    "</div>" +
    '<div class="stats">' +
    '<div class="stat"><div class="label">My invoices</div><div class="value">' +
    invoices.length +
    "</div></div>" +
    "</div>";

  document.getElementById("up-submit").addEventListener("click", uploadInvoice);
}

function uploadInvoice() {
  var picker = document.getElementById("up-file");
  var file = picker.files[0];
  if (!file) {
    toast("Please choose a file first", "error");
    return;
  }
  var fd = new FormData();
  fd.append("upload", file);
  var notes = document.getElementById("up-notes").value.trim();
  if (notes) fd.append("notes", notes);

  var btn = document.getElementById("up-submit");
  btn.disabled = true;
  api("/clients/me/invoices/upload", { method: "POST", body: fd })
    .then(function (inv) {
      toast("Invoice " + inv.invoice_number + " uploaded", "success");
      location.href = page("client-invoice-detail") + "?id=" + inv.id;
    })
    .catch(function (err) {
      toast(err.message, "error");
      btn.disabled = false;
    });
}

function renderStatusRow(content, invoices) {
  var counts = { PENDING: 0, PROCESSING: 0, COMPLETED: 0, REVIEW: 0, CANCELLED: 0 };
  invoices.forEach(function (inv) {
    if (counts.hasOwnProperty(inv.status)) counts[inv.status] += 1;
  });
  var chips = STATUS_ORDER.map(function (status) {
    return (
      '<span class="badge ' + status + '">' + status + ": " + counts[status] +
      "</span>"
    );
  }).join(" ");
  content.insertAdjacentHTML(
    "beforeend",
    '<div class="card"><h3>My invoices by status</h3><div class="legend">' +
      chips +
      "</div></div>"
  );
}

function renderRecent(content, invoices) {
  var rows = invoices
    .slice(0, 5)
    .map(function (inv) {
      return (
        "<tr>" +
        '<td class="mono"><a href="' + page("client-invoice-detail") + "?id=" + inv.id + '">' +
        esc(inv.invoice_number) + "</a></td>" +
        "<td>" + fmtDate(inv.invoice_date) + "</td>" +
        "<td>" + statusBadge(inv.status) + "</td>" +
        '<td class="num">' + fmtMoney(inv.total_amount, inv.currency) + "</td>" +
        "</tr>"
      );
    })
    .join("");
  content.insertAdjacentHTML(
    "beforeend",
    '<div class="card"><h3>Recent invoices</h3>' +
      '<div class="table-wrap"><table class="data">' +
      "<thead><tr><th>Number</th><th>Date</th><th>Status</th>" +
      '<th class="num">Total</th></tr></thead>' +
      "<tbody>" +
      (rows || '<tr><td colspan="4" class="empty">No invoices yet. Upload your first invoice above.</td></tr>') +
      "</tbody></table></div>" +
      '<a class="btn small" href="' + page("client-invoices") + '">View all invoices</a></div>'
  );
}

loadClientDashboard();
