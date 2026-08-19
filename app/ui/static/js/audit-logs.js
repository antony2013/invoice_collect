"use strict";

initShell("audit-logs.xhtml", "Audit Logs");

var state = { page: 1, pageSize: 20, action: "", resourceType: "", total: 0 };

function content() {
  return document.getElementById("content");
}

async function loadLogs() {
  var box = content();
  box.innerHTML = '<div class="loading">Loading audit logs&hellip;</div>';
  try {
    var params = {
      page: state.page,
      page_size: state.pageSize,
      action: state.action,
      resource_type: state.resourceType,
    };
    var data = await api("/audit-logs" + qs(params));
    state.total = data.total;
    renderLogs(data.items);
  } catch (err) {
    box.innerHTML = '<div class="empty">' + esc(err.message) + "</div>";
  }
}

function renderLogs(entries) {
  var html =
    '<div class="toolbar">' +
    '<input id="f-action" type="text" placeholder="Filter by action" value="' + esc(state.action) + '" />' +
    '<input id="f-type" type="text" placeholder="Filter by resource type" value="' + esc(state.resourceType) + '" />' +
    '<button class="btn" id="btn-apply">Apply</button>' +
    '<span class="spacer"></span></div>' +
    '<div class="card"><div class="table-wrap"><table class="data"><thead><tr>' +
    "<th>When</th><th>Actor</th><th>Action</th><th>Resource</th><th>Details</th>" +
    "</tr></thead><tbody>";

  if (!entries.length) {
    html += '<tr><td colspan="5" class="empty">No audit log entries.</td></tr>';
  } else {
    entries.forEach(function (e) {
      var details = "-";
      if (e.details) {
        details = Object.keys(e.details)
          .map(function (k) { return k + "=" + e.details[k]; })
          .join(", ");
      }
      html +=
        "<tr><td>" + fmtDateTime(e.created_at) + "</td>" +
        "<td>" + esc(e.actor_name || "system") + "</td>" +
        '<td class="mono">' + esc(e.action) + "</td>" +
        "<td>" + esc(e.resource_type || "-") + "</td>" +
        '<td class="mono">' + esc(details) + "</td></tr>";
    });
  }

  html += "</tbody></table></div>" + renderPagination() + "</div>";
  content().innerHTML = html;

  document.getElementById("btn-apply").addEventListener("click", applyFilters);
  document.getElementById("f-action").addEventListener("keydown", function (event) {
    if (event.key === "Enter") applyFilters();
  });
  document.getElementById("f-type").addEventListener("keydown", function (event) {
    if (event.key === "Enter") applyFilters();
  });

  var prev = document.getElementById("pg-prev");
  var next = document.getElementById("pg-next");
  if (prev) prev.addEventListener("click", function () { state.page -= 1; loadLogs(); });
  if (next) next.addEventListener("click", function () { state.page += 1; loadLogs(); });
}

function applyFilters() {
  state.action = document.getElementById("f-action").value.trim();
  state.resourceType = document.getElementById("f-type").value.trim();
  state.page = 1;
  loadLogs();
}

function renderPagination() {
  var pages = Math.max(1, Math.ceil(state.total / state.pageSize));
  return (
    '<div class="pagination">' +
    "<span>" + state.total + " entries</span>" +
    '<button class="btn small" id="pg-prev" ' + (state.page <= 1 ? "disabled=\"disabled\"" : "") + ">Previous</button>" +
    "<span>Page " + state.page + " / " + pages + "</span>" +
    '<button class="btn small" id="pg-next" ' + (state.page >= pages ? "disabled=\"disabled\"" : "") + ">Next</button>" +
    "</div>"
  );
}

loadLogs();
