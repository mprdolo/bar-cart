/* ===========================
   Bar Cart — Results Page
   =========================== */

(function () {
    'use strict';

    var $ = BarCart.$;
    var $$ = BarCart.$$;
    var api = BarCart.api;
    var showToast = BarCart.showToast;

    var resultsContainer = $('#results-container');
    var loadingEl = $('#loading-results');
    var emptyEl = $('#empty-results');
    var summaryEl = $('#results-summary');
    var filterBar = $('#filter-bar');
    var sortSelect = $('#sort-select');
    var spiritFilter = $('#spirit-filter');
    var ingredientSearch = $('#ingredient-search');
    var ingredientDropdown = $('#ingredient-dropdown');
    var ingredientChipsEl = $('#ingredient-chips');

    var allResults = [];
    var currentFilter = 'all';
    var stockedNames = [];
    var selectedIngredients = [];

    // Restore filter/sort state from sessionStorage
    var savedFilter = sessionStorage.getItem('bc_filter');
    var savedSort = sessionStorage.getItem('bc_sort');
    var savedSpirit = sessionStorage.getItem('bc_spirit');
    var savedIngredients = sessionStorage.getItem('bc_ingredients');
    if (savedFilter) currentFilter = savedFilter;
    if (savedSort) sortSelect.value = savedSort;
    if (savedIngredients) {
        try { selectedIngredients = JSON.parse(savedIngredients); } catch (e) { selectedIngredients = []; }
    }

    loadResults();
    loadStockedNames();

    async function loadStockedNames() {
        try {
            var result = await api('/api/bar/stocked-names');
            stockedNames = result.data || [];
        } catch (err) {
            stockedNames = [];
        }
    }

    async function loadResults() {
        try {
            var result = await api('/api/shake');
            var data = result.data;

            allResults = [];
            for (var i = 0; i < data.perfect.length; i++) allResults.push(data.perfect[i]);
            for (var i = 0; i < data.substitute.length; i++) allResults.push(data.substitute[i]);
            for (var i = 0; i < data.close.length; i++) allResults.push(data.close[i]);

            loadingEl.style.display = 'none';

            if (allResults.length === 0) {
                emptyEl.style.display = 'block';
                summaryEl.textContent = '';
                return;
            }

            summaryEl.innerHTML = '<strong>' + data.perfect.length + '</strong> perfect, ' +
                '<strong>' + data.substitute.length + '</strong> with subs, ' +
                '<strong>' + data.close.length + '</strong> almost';

            populateSpiritFilter();

            // Restore spirit filter after populating options
            if (savedSpirit) spiritFilter.value = savedSpirit;

            // Restore active filter button
            if (savedFilter) {
                var btns = $$('.filter-btn');
                for (var i = 0; i < btns.length; i++) {
                    btns[i].classList.toggle('active', btns[i].dataset.filter === currentFilter);
                }
            }

            // Restore ingredient chips
            renderChips();

            renderResults();

            // Restore scroll position
            var savedScroll = sessionStorage.getItem('bc_scroll');
            if (savedScroll) {
                setTimeout(function () { window.scrollTo(0, parseInt(savedScroll)); }, 50);
                sessionStorage.removeItem('bc_scroll');
            }
        } catch (err) {
            loadingEl.style.display = 'none';
            emptyEl.style.display = 'block';
            showToast(err.message, true);
        }
    }

    function populateSpiritFilter() {
        var spirits = {};
        for (var i = 0; i < allResults.length; i++) {
            var s = allResults[i].primary_spirit;
            if (s) spirits[s] = (spirits[s] || 0) + 1;
        }
        var keys = Object.keys(spirits).sort();
        for (var i = 0; i < keys.length; i++) {
            var opt = document.createElement('option');
            opt.value = keys[i];
            opt.textContent = keys[i] + ' (' + spirits[keys[i]] + ')';
            spiritFilter.appendChild(opt);
        }
    }

    function getFiltered() {
        var filtered = allResults;
        if (currentFilter !== 'all') {
            filtered = filtered.filter(function (c) { return c.tier === currentFilter; });
        }
        var spirit = spiritFilter.value;
        if (spirit !== 'all') {
            filtered = filtered.filter(function (c) { return c.primary_spirit === spirit; });
        }
        // Ingredient chip filter (AND logic)
        if (selectedIngredients.length > 0) {
            filtered = filtered.filter(function (c) {
                if (!c.ingredient_names) return false;
                var namesLower = c.ingredient_names.map(function (n) { return n.toLowerCase(); });
                for (var i = 0; i < selectedIngredients.length; i++) {
                    var sel = selectedIngredients[i].toLowerCase();
                    var found = false;
                    for (var j = 0; j < namesLower.length; j++) {
                        if (namesLower[j].indexOf(sel) !== -1) { found = true; break; }
                    }
                    if (!found) return false;
                }
                return true;
            });
        }
        return filtered;
    }

    function getSorted(list) {
        var sorted = list.slice();
        var sortBy = sortSelect.value;
        if (sortBy === 'name') {
            sorted.sort(function (a, b) { return a.name.toLowerCase().localeCompare(b.name.toLowerCase()); });
        } else if (sortBy === 'tier') {
            var tierOrder = { perfect: 0, substitute: 1, close: 2 };
            sorted.sort(function (a, b) {
                var d = tierOrder[a.tier] - tierOrder[b.tier];
                return d !== 0 ? d : a.name.toLowerCase().localeCompare(b.name.toLowerCase());
            });
        } else if (sortBy === 'ingredients') {
            sorted.sort(function (a, b) {
                var d = a.total_ingredients - b.total_ingredients;
                return d !== 0 ? d : a.name.toLowerCase().localeCompare(b.name.toLowerCase());
            });
        } else if (sortBy === 'rating') {
            sorted.sort(function (a, b) {
                var ra = a.avg_rating || 0;
                var rb = b.avg_rating || 0;
                if (ra !== rb) return rb - ra;
                return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
            });
        }
        return sorted;
    }

    function filterSpiritFromIngredients(ingredientNames, primarySpirit) {
        if (!primarySpirit || !ingredientNames) return ingredientNames;
        var spiritLower = primarySpirit.toLowerCase();
        var skipped = false;
        return ingredientNames.filter(function (name) {
            if (!skipped && name.toLowerCase().indexOf(spiritLower) !== -1) {
                skipped = true;
                return false;
            }
            return true;
        });
    }

    function renderResults() {
        var filtered = getSorted(getFiltered());

        if (filtered.length === 0) {
            resultsContainer.innerHTML = '<div class="empty-state"><p>No cocktails match this filter.</p></div>';
            return;
        }

        var html = '<div class="cocktail-grid">';
        for (var i = 0; i < filtered.length; i++) {
            var c = filtered[i];
            html += '<a class="cocktail-card" href="/recipe/' + c.id + '" data-cocktail-id="' + c.id + '">';
            html += '<span class="card-badge badge-' + c.tier + '">' + tierLabel(c.tier) + '</span>';
            html += '<span class="card-name">' + escHtml(c.name) + '</span>';
            html += '<span class="card-meta">';
            if (c.primary_spirit) {
                html += '<span class="card-spirit">' + escHtml(c.primary_spirit) + '</span>';
            }
            if (c.avg_rating) {
                html += '<span class="card-rating">&#127820; ' + c.avg_rating + '</span>';
            }
            html += '</span>';
            var displayIngredients = filterSpiritFromIngredients(c.ingredient_names, c.primary_spirit);
            if (displayIngredients && displayIngredients.length > 0) {
                html += '<span class="card-ingredients">';
                for (var j = 0; j < displayIngredients.length; j++) {
                    if (j > 0) html += '<span class="card-ing-sep">&middot;</span>';
                    html += '<span>' + escHtml(displayIngredients[j]) + '</span>';
                }
                html += '</span>';
            }
            if (c.tier === 'close' && c.missing_ingredients && c.missing_ingredients.length > 0) {
                html += '<span class="card-missing">Need: ' + escHtml(c.missing_ingredients[0].name) + '</span>';
            }
            html += '</a>';
        }
        html += '</div>';
        resultsContainer.innerHTML = html;

        // Save state and scroll position when clicking a card
        var cards = $$('.cocktail-card');
        for (var i = 0; i < cards.length; i++) {
            cards[i].addEventListener('click', saveState);
        }
    }

    function saveState() {
        sessionStorage.setItem('bc_scroll', window.scrollY);
        sessionStorage.setItem('bc_filter', currentFilter);
        sessionStorage.setItem('bc_sort', sortSelect.value);
        sessionStorage.setItem('bc_spirit', spiritFilter.value);
        sessionStorage.setItem('bc_ingredients', JSON.stringify(selectedIngredients));
    }

    function tierLabel(tier) {
        if (tier === 'perfect') return 'Perfect';
        if (tier === 'substitute') return 'With Subs';
        if (tier === 'close') return 'Almost';
        return tier;
    }

    // --- Ingredient typeahead & chips ---

    function renderChips() {
        if (!ingredientChipsEl) return;
        var html = '';
        for (var i = 0; i < selectedIngredients.length; i++) {
            html += '<span class="ingredient-chip">' + escHtml(selectedIngredients[i]) +
                '<button class="ingredient-chip-remove" data-ingredient="' + escHtml(selectedIngredients[i]) + '">&times;</button></span>';
        }
        ingredientChipsEl.innerHTML = html;

        var removeBtns = ingredientChipsEl.querySelectorAll('.ingredient-chip-remove');
        for (var i = 0; i < removeBtns.length; i++) {
            removeBtns[i].addEventListener('click', function (e) {
                var name = e.target.dataset.ingredient;
                selectedIngredients = selectedIngredients.filter(function (n) { return n !== name; });
                renderChips();
                renderResults();
            });
        }
    }

    function showDropdown(query) {
        if (!ingredientDropdown) return;
        if (!query || stockedNames.length === 0) {
            ingredientDropdown.style.display = 'none';
            return;
        }
        var q = query.toLowerCase();
        var matches = stockedNames.filter(function (name) {
            if (selectedIngredients.indexOf(name) !== -1) return false;
            return name.toLowerCase().indexOf(q) !== -1;
        });
        if (matches.length === 0) {
            ingredientDropdown.style.display = 'none';
            return;
        }
        // Limit to 10
        matches = matches.slice(0, 10);
        var html = '';
        for (var i = 0; i < matches.length; i++) {
            html += '<div class="ingredient-dropdown-item" data-name="' + escHtml(matches[i]) + '">' + escHtml(matches[i]) + '</div>';
        }
        ingredientDropdown.innerHTML = html;
        ingredientDropdown.style.display = 'block';

        var items = ingredientDropdown.querySelectorAll('.ingredient-dropdown-item');
        for (var i = 0; i < items.length; i++) {
            items[i].addEventListener('mousedown', function (e) {
                e.preventDefault();
                selectIngredient(e.target.dataset.name);
            });
        }
    }

    function selectIngredient(name) {
        if (selectedIngredients.indexOf(name) === -1) {
            selectedIngredients.push(name);
        }
        if (ingredientSearch) ingredientSearch.value = '';
        if (ingredientDropdown) ingredientDropdown.style.display = 'none';
        renderChips();
        renderResults();
    }

    if (ingredientSearch) {
        ingredientSearch.addEventListener('input', function () {
            showDropdown(ingredientSearch.value.trim());
        });

        ingredientSearch.addEventListener('focus', function () {
            if (ingredientSearch.value.trim()) {
                showDropdown(ingredientSearch.value.trim());
            }
        });

        ingredientSearch.addEventListener('blur', function () {
            // Delay to allow click on dropdown item
            setTimeout(function () { if (ingredientDropdown) ingredientDropdown.style.display = 'none'; }, 150);
        });
    }

    // Filter buttons
    filterBar.addEventListener('click', function (e) {
        var btn = e.target.closest('.filter-btn');
        if (!btn) return;
        var btns = $$('.filter-btn');
        for (var i = 0; i < btns.length; i++) btns[i].classList.remove('active');
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        if (currentFilter === 'dismissed') {
            loadDismissed();
        } else {
            renderResults();
        }
    });

    sortSelect.addEventListener('change', renderResults);
    spiritFilter.addEventListener('change', renderResults);

    async function loadDismissed() {
        try {
            var result = await api('/api/dismissed');
            var items = result.data;
            if (!items || items.length === 0) {
                resultsContainer.innerHTML = '<div class="empty-state"><p>No dismissed cocktails.</p></div>';
                return;
            }
            renderDismissed(items);
        } catch (err) {
            showToast(err.message, true);
        }
    }

    function renderDismissed(items) {
        var html = '<div class="cocktail-grid">';
        for (var i = 0; i < items.length; i++) {
            var c = items[i];
            html += '<div class="cocktail-card dismissed-card" data-cocktail-id="' + c.id + '">';
            html += '<span class="card-badge badge-dismissed">Dismissed</span>';
            html += '<a class="card-name" href="/recipe/' + c.id + '">' + escHtml(c.name) + '</a>';
            html += '<span class="card-meta">';
            if (c.primary_spirit) {
                html += '<span class="card-spirit">' + escHtml(c.primary_spirit) + '</span>';
            }
            html += '</span>';
            html += '<button class="btn btn-restore btn-small" data-restore-id="' + c.id + '">Restore</button>';
            html += '</div>';
        }
        html += '</div>';
        resultsContainer.innerHTML = html;

        // Attach restore handlers
        var btns = resultsContainer.querySelectorAll('[data-restore-id]');
        for (var i = 0; i < btns.length; i++) {
            btns[i].addEventListener('click', onRestoreFromList);
        }
    }

    async function onRestoreFromList(e) {
        var id = e.target.dataset.restoreId;
        try {
            await api('/api/recipe/' + id + '/restore', 'POST');
            showToast('Cocktail restored');
            var card = resultsContainer.querySelector('.dismissed-card[data-cocktail-id="' + id + '"]');
            if (card) card.remove();
            // Check if list is now empty
            if (!resultsContainer.querySelector('.dismissed-card')) {
                resultsContainer.innerHTML = '<div class="empty-state"><p>No dismissed cocktails.</p></div>';
            }
        } catch (err) {
            showToast(err.message, true);
        }
    }

    function escHtml(s) {
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }
})();
