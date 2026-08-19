"use strict";

location.replace(page(isLoggedIn() ? "dashboard" : "login"));
