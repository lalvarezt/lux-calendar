(function () {
  var root = document.documentElement;
  var themeToggle = document.getElementById("theme-toggle");
  var themeLabel = themeToggle ? themeToggle.querySelector(".theme-toggle-label") : null;
  var storageKey = "lux-calendar-theme";
  var webcalLink = document.getElementById("webcal-link");
  var entriesGrid = document.getElementById("entries-grid");
  var cards = entriesGrid
    ? Array.prototype.slice.call(entriesGrid.querySelectorAll(".entry-card"))
    : [];
  var searchInput = document.getElementById("entry-search");
  var filtersContainer = document.getElementById("category-filters");
  var resultsCount = document.getElementById("results-count");

  if (webcalLink) {
    var icsPath = webcalLink.getAttribute("href") || "";
    var absoluteUrl = new URL(icsPath, window.location.href).toString();
    var webcalUrl = absoluteUrl.replace(/^https?:\/\//, "webcal://");
    webcalLink.setAttribute("href", webcalUrl);
    webcalLink.textContent = webcalUrl;
  }

  var storedTheme = readStorage(storageKey);
  var initialTheme = storedTheme === "dark" || storedTheme === "light" ? storedTheme : "light";
  applyTheme(initialTheme);

  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      var currentTheme = root.getAttribute("data-theme") === "dark" ? "dark" : "light";
      var nextTheme = currentTheme === "dark" ? "light" : "dark";
      applyTheme(nextTheme);
      writeStorage(storageKey, nextTheme);
    });
  }

  if (cards.length > 0) {
    prepareCards(cards);
    setupFilters(cards);
  }

  function prepareCards(cardList) {
    cardList.forEach(function (card, index) {
      card.style.setProperty("--entry-index", String(Math.min(index, 18)));
    });
  }

  function setupFilters(cardList) {
    var categoryLabels = {};
    var categoryCounts = {};

    var states = cardList.map(function (card) {
      var tags = Array.prototype.slice.call(card.querySelectorAll(".entry-tag"));
      var categories = [];

      tags.forEach(function (tag) {
        var label = (tag.textContent || "").trim();
        var key = normalizeToken(label);
        if (!key || categories.indexOf(key) !== -1) {
          return;
        }

        categories.push(key);
        if (!categoryLabels[key]) {
          categoryLabels[key] = label;
        }
        categoryCounts[key] = (categoryCounts[key] || 0) + 1;
      });

      return {
        card: card,
        categories: categories,
        searchableText: normalizeToken(card.textContent || ""),
      };
    });

    var sortedCategories = Object.keys(categoryLabels).sort(function (left, right) {
      return categoryLabels[left].localeCompare(categoryLabels[right]);
    });
    var activeCategory = "all";

    renderFilterButtons(sortedCategories);

    if (searchInput) {
      searchInput.addEventListener("input", applyFilters);
      searchInput.addEventListener("search", applyFilters);
    }

    applyFilters();

    function renderFilterButtons(categoryKeys) {
      if (!filtersContainer) {
        return;
      }

      filtersContainer.innerHTML = "";
      addFilterButton("all", "All", cardList.length);
      categoryKeys.forEach(function (key) {
        addFilterButton(key, categoryLabels[key], categoryCounts[key] || 0);
      });
      syncFilterButtons();
    }

    function addFilterButton(key, label, count) {
      if (!filtersContainer) {
        return;
      }

      var button = document.createElement("button");
      button.type = "button";
      button.className = "filter-chip";
      button.setAttribute("data-category", key);
      button.setAttribute("aria-pressed", "false");
      button.textContent = label + " (" + count + ")";
      button.addEventListener("click", function () {
        activeCategory = key;
        syncFilterButtons();
        applyFilters();
      });
      filtersContainer.appendChild(button);
    }

    function syncFilterButtons() {
      if (!filtersContainer) {
        return;
      }

      var buttons = filtersContainer.querySelectorAll(".filter-chip");
      Array.prototype.forEach.call(buttons, function (button) {
        var isActive = button.getAttribute("data-category") === activeCategory;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      });
    }

    function applyFilters() {
      var rawQuery = searchInput ? searchInput.value.trim() : "";
      var query = normalizeToken(rawQuery);
      var visibleCount = 0;

      states.forEach(function (state) {
        var matchesCategory = activeCategory === "all" || state.categories.indexOf(activeCategory) !== -1;
        var matchesQuery = !query || state.searchableText.indexOf(query) !== -1;
        var shouldShow = matchesCategory && matchesQuery;

        state.card.hidden = !shouldShow;
        if (shouldShow) {
          visibleCount += 1;
        }
      });

      var activeCategoryLabel = activeCategory === "all" ? "" : categoryLabels[activeCategory] || activeCategory;
      updateResultLabel(visibleCount, states.length, rawQuery, activeCategoryLabel);
    }
  }

  function updateResultLabel(visibleCount, totalCount, query, categoryLabel) {
    if (!resultsCount) {
      return;
    }

    var parts = [visibleCount + " of " + totalCount + " entries shown"];
    if (categoryLabel) {
      parts.push("category: " + categoryLabel);
    }
    if (query) {
      parts.push('search: "' + query + '"');
    }

    resultsCount.textContent = parts.join(" | ");
  }

  function normalizeToken(value) {
    return value.toLowerCase().replace(/\s+/g, " ").trim();
  }

  function readStorage(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (_error) {
      return null;
    }
  }

  function writeStorage(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (_error) {
    }
  }

  function applyTheme(theme) {
    var safeTheme = theme === "dark" ? "dark" : "light";
    var labels = {
      light: "Parchment",
      dark: "Ink",
    };

    root.setAttribute("data-theme", safeTheme);

    if (!themeToggle || !themeLabel) {
      return;
    }

    var isDark = safeTheme === "dark";
    themeLabel.textContent = labels[safeTheme];
    themeToggle.setAttribute("aria-pressed", isDark ? "true" : "false");
    themeToggle.setAttribute("aria-label", isDark ? "Switch to parchment theme" : "Switch to ink theme");
  }
})();
