(function () {
  var root = document.documentElement;
  var themeToggle = document.getElementById("theme-toggle");
  var themeLabel = themeToggle ? themeToggle.querySelector(".theme-toggle-label") : null;
  var storageKey = "lux-calendar-theme";
  var webcalLink = document.getElementById("webcal-link");

  if (webcalLink) {
    var icsPath = webcalLink.getAttribute("href") || "";
    var absoluteUrl = new URL(icsPath, window.location.href).toString();
    var webcalUrl = absoluteUrl.replace(/^https?:\/\//, "webcal://");
    webcalLink.setAttribute("href", webcalUrl);
    webcalLink.textContent = webcalUrl;
  }

  var storedTheme = null;
  try {
    storedTheme = window.localStorage.getItem(storageKey);
  } catch (_error) {
    storedTheme = null;
  }

  var initialTheme = storedTheme === "light" || storedTheme === "dark" ? storedTheme : "dark";
  applyTheme(initialTheme);

  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      var currentTheme = root.getAttribute("data-theme") === "light" ? "light" : "dark";
      var nextTheme = currentTheme === "dark" ? "light" : "dark";
      applyTheme(nextTheme);

      try {
        window.localStorage.setItem(storageKey, nextTheme);
      } catch (_error) {
      }
    });
  }

  function applyTheme(theme) {
    var safeTheme = theme === "light" ? "light" : "dark";
    root.setAttribute("data-theme", safeTheme);

    if (!themeToggle || !themeLabel) {
      return;
    }

    var isDark = safeTheme === "dark";
    themeLabel.textContent = isDark ? "Dark" : "Light";
    themeToggle.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
    themeToggle.setAttribute("aria-pressed", isDark ? "false" : "true");
  }
})();
