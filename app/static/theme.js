// Applies the saved theme before the page is painted (loaded in <head> without defer).
(function () {
  try {
    var theme = localStorage.getItem("theme");
    if (theme === "light" || theme === "dark") {
      document.documentElement.setAttribute("data-theme", theme);
    }
  } catch (e) {
    // Storage can be blocked (private mode); the system theme is used then.
  }
})();
