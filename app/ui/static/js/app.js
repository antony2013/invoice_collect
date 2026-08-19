"use strict";

var API_BASE = "/api/v1";

/* ---------------- auth storage ---------------- */

function getToken() {
  return localStorage.getItem("invoice_token");
}

function setToken(token) {
  localStorage.setItem("invoice_token", token);
}

function clearToken() {
  localStorage.removeItem("invoice_token");
}

function isLoggedIn() {
  return !!getToken();
}

function page(name) {
  return "/ui/" + name + ".xhtml";
}

function requireAuth() {
  if (!isLoggedIn()) {
    location.href = page("login");
  }
}

/* ---------------- api client ---------------- */

function detailMessage(detail) {
  if (detail === null || detail === undefined) return "Request failed";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map(function (e) {
        var field = (e.loc || []).slice(1).join(".");
        return (field ? field + ": " : "") + e.msg;
      })
      .join("; ");
  }
  return "Request failed";
}

async function api(path, options) {
  options = options || {};
  var headers = Object.assign({}, options.headers || {});
  var token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  var body = options.body;
  if (body && !(body instanceof FormData) && typeof body !== "string") {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  var resp = await fetch(API_BASE + path, {
    method: options.method || "GET",
    headers: headers,
    body: body,
  });
  if (resp.status === 401) {
    clearToken();
    if (!/login\.xhtml$/.test(location.pathname)) {
      location.href = page("login");
    }
    var err = new Error("Session expired");
    err.status = 401;
    throw err;
  }
  if (resp.status === 204) return null;
  var data = null;
  try {
    data = await resp.json();
  } catch (e) {
    data = null;
  }
  if (!resp.ok) {
    var err2 = new Error(detailMessage(data && data.detail));
    err2.status = resp.status;
    throw err2;
  }
  return data;
}

/* ---------------- dom / utils ---------------- */

function esc(value) {
  return String(value === null || value === undefined ? "" : value).replace(
    /[&<>"']/g,
    function (c) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[c];
    }
  );
}

function fmtMoney(amount, currency) {
  var n = Number(amount || 0);
  return (currency || "USD") + " " + n.toFixed(2);
}

function fmtDate(iso) {
  if (!iso) return "-";
  return String(iso).slice(0, 10);
}

function fmtDateTime(iso) {
  if (!iso) return "-";
  return String(iso).replace("T", " ").replace(/\.\d+.*$/, "");
}

function fmtBytes(bytes) {
  if (!bytes) return "0 B";
  var units = ["B", "KB", "MB", "GB"];
  var i = 0;
  var n = bytes;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i += 1;
  }
  return n.toFixed(i ? 1 : 0) + " " + units[i];
}

function statusBadge(status) {
  return '<span class="badge ' + esc(status) + '">' + esc(status) + "</span>";
}

/* ---------------- toast ---------------- */

function toast(msg, type) {
  var box = document.getElementById("toast-box");
  if (!box) {
    box = document.createElement("div");
    box.id = "toast-box";
    box.className = "toast-box";
    document.body.appendChild(box);
  }
  var t = document.createElement("div");
  t.className = "toast " + (type || "info");
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(function () {
    t.classList.add("out");
    setTimeout(function () {
      t.remove();
    }, 320);
  }, 4200);
}

/* ---------------- shell (sidebar + topbar) ---------------- */

var NAV_OWNER = [
  { href: page("dashboard"), icon: "◧", label: "Dashboard" },
  { href: page("invoices"), icon: "◫", label: "Invoices" },
  { href: page("clients"), icon: "☰", label: "Clients" },
  { href: page("staff"), icon: "♟", label: "Staff" },
  { href: page("audit-logs"), icon: "≡", label: "Audit Logs" },
  { href: page("organization"), icon: "⌂", label: "Organization" },
];

var NAV_STAFF = [
  { href: page("dashboard"), icon: "◧", label: "Dashboard" },
  { href: page("invoices"), icon: "◫", label: "Invoices" },
];

var NAV_CLIENT = [
  { href: page("client-dashboard"), icon: "◧", label: "Client Dashboard" },
  { href: page("client-invoices"), icon: "◫", label: "My Invoices" },
];

var ACTIVE_PAGE = null;

function currentRole() {
  return (window.CURRENT_USER && window.CURRENT_USER.role) || "STAFF";
}

function getCurrentUser() {
  if (window.CURRENT_USER) return Promise.resolve(window.CURRENT_USER);
  return api("/auth/me").then(function (me) {
    window.CURRENT_USER = me;
    return me;
  });
}

function renderSidebar(active) {
  ACTIVE_PAGE = active;
  var role = currentRole();
  var items =
    role === "OWNER" ? NAV_OWNER : role === "CLIENT" ? NAV_CLIENT : NAV_STAFF;
  var html =
    '<div class="brand"><span class="logo">I</span><span>InvoiceOS</span></div>' +
    '<nav class="nav">';
  items.forEach(function (item) {
    html +=
      '<a href="' + item.href + '"' +
      (item.href === page(active) ? ' class="active"' : "") +
      '><span class="ic">' + item.icon + "</span><span>" + item.label + "</span></a>";
  });
  html +=
    '</nav><div class="sidebar-foot">Invoice Management SaaS<br />v0.1.0</div>';
  var sb = document.getElementById("sidebar");
  if (sb) sb.innerHTML = html;
}

function renderTopbar(title) {
  var tb = document.getElementById("topbar");
  if (!tb) return;
  tb.innerHTML =
    '<div class="page-title">' + esc(title) + "</div>" +
    '<div class="user-box"><span id="user-name">…</span>' +
    '<button class="btn small" id="logout-btn">Log out</button></div>';
  document.getElementById("logout-btn").addEventListener("click", function () {
    api("/auth/logout", { method: "POST" })
      .catch(function () {})
      .then(function () {
        clearToken();
        location.href = page("login");
      });
  });
  api("/auth/me")
    .then(function (me) {
      window.CURRENT_USER = me;
      document.getElementById("user-name").textContent =
        me.full_name + " (" + me.role + ")";
      if (ACTIVE_PAGE) renderSidebar(ACTIVE_PAGE);
    })
    .catch(function () {});
}

function initShell(active, title) {
  requireAuth();
  renderSidebar(active);
  renderTopbar(title);
}

/* ---------------- misc ---------------- */

function qs(params) {
  var parts = [];
  Object.keys(params).forEach(function (key) {
    var v = params[key];
    if (v !== null && v !== undefined && v !== "") {
      parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(v));
    }
  });
  return parts.length ? "?" + parts.join("&") : "";
}

function getParam(name) {
  var m = new RegExp("[?&]" + encodeURIComponent(name) + "=([^&]*)").exec(
    location.search
  );
  return m ? decodeURIComponent(m[1]) : null;
}
