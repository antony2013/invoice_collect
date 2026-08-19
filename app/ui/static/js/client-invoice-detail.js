"use strict";

initShell("client-invoice-detail.xhtml", "Invoice");

var invoiceId = getParam("id");
var current = null;

function content() {
  return document.getElementById("content");
}

async function loadDetail() {
  var box = content();
  box.innerHTML = '<div class="loading">Loading invoice&hellip;</div>';
  try {
    var me = await getCurrentUser();
    if (me.role !== "CLIENT") {
      box.innerHTML = '<div class="empty">Access denied.</div>';
      return;
    }
    current = await api("/clients/me/invoices/" + invoiceId);
    renderAll();
  } catch (err) {
    box.innerHTML = '<div class="empty">' + esc(err.message) + "</div>";
  }
}

function renderAll() {
  var inv = current;
  var html =
    '<div class="btn-row" style="margin-bottom: 14px;">' +
    '<a class="btn" href="' + page("client-invoices") + '">← My invoices</a>' +
    "</div>" +
    '<div class="card">' +
    '<div class="btn-row" style="justify-content: space-between;">' +
    '<div><h2 class="mono">' + esc(inv.invoice_number) + "</h2>" +
    '<span class="muted">Submitted ' + fmtDateTime(inv.created_at) + "</span></div>" +
    statusBadge(inv.status) +
    "</div>" +
    '<div class="legend" style="margin-top: 12px;">' +
    '<span class="li">Date: ' + fmtDate(inv.invoice_date) + "</span>" +
    '<span class="li">Currency: ' + esc(inv.currency) + "</span>" +
    '<span class="li">Total: <strong>' + fmtMoney(inv.total_amount, inv.currency) + "</strong></span>" +
    "</div>" +
    (inv.notes ? '<p class="muted" style="margin-top: 10px;">' + esc(inv.notes) + "</p>" : "") +
    "</div>" +
    '<div class="card"><h3>Files</h3>' +
    '<div class="btn-row" style="margin-bottom: 10px;">' +
    '<button class="btn small" id="btn-upload">Upload another file</button>' +
    "</div>" +
    '<div class="file-list" id="file-list"></div></div>';

  content().innerHTML = html;
  renderFiles();
  wireActions();
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
    API_BASE + "/clients/me/invoices/" + invoiceId + "/files/" + fileId + "/download",
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
        '<span class="fmeta">' + fmtBytes(f.size_bytes) + " · " + fmtDateTime(f.created_at) + "</span>" +
        '<button class="btn small" data-dl="' + f.id + '">Download</button>' +
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
}

function wireActions() {
  document.getElementById("btn-upload").addEventListener("click", function () {
    document.getElementById("file-input").click();
  });
  document.getElementById("file-input").addEventListener("change", async function () {
    var file = this.files[0];
    if (!file) return;
    var fd = new FormData();
    fd.append("upload", file);
    try {
      await api("/clients/me/invoices/" + invoiceId + "/files", { method: "POST", body: fd });
      toast("File uploaded", "success");
      this.value = "";
      loadDetail();
    } catch (err) {
      toast(err.message, "error");
      this.value = "";
    }
  });
}

loadDetail();
