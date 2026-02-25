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

    var allResults = [];
    var currentFilter = 'all';

    // Restore filter/sort state from sessionStorage
    var savedFilter = sessionStorage.getItem('bc_filter');
    var savedSort = sessionStorage.getItem('bc_sort');
    var savedSpirit = sessionStorage.getItem('bc_spirit');
    if (savedFilter) currentFilter = savedFilter;
    if (savedSort) sortSelect.value = savedSort;

    loadResults();

    async function loadResults() {
        try {
            // Use cached results if we're coming back from a recipe
            var cached = sessionStorage.getItem('bc_results');
            var data;
            if (cached) {
                data = JSON.parse(cached);
                sessionStorage.removeItem('bc_results');
            } else {
                var result = await api('/api/shake');
                data = result.data;
            }

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
            html += '<div class="card-name">' + escHtml(c.name) + '</div>';
            html += '<div class="card-meta">';
            html += '<span class="card-badge badge-' + c.tier + '">' + tierLabel(c.tier) + '</span>';
            if (c.primary_spirit) {
                html += '<span class="card-spirit">' + escHtml(c.primary_spirit) + '</span>';
            }
            if (c.avg_rating) {
                html += '<span class="card-rating">&#127820; ' + c.avg_rating + '</span>';
            }
            html += '</div>';
            // Ingredient list
            if (c.ingredient_names && c.ingredient_names.length > 0) {
                html += '<div class="card-ingredients">';
                for (var j = 0; j < c.ingredient_names.length; j++) {
                    if (j > 0) html += '<span class="card-ing-sep">&middot;</span>';
                    html += '<span>' + escHtml(c.ingredient_names[j]) + '</span>';
                }
                html += '</div>';
            }
            if (c.tier === 'close' && c.missing_ingredients && c.missing_ingredients.length > 0) {
                html += '<div class="card-missing">Need: ' + escHtml(c.missing_ingredients[0].name) + '</div>';
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
        // Cache the results so we don't re-fetch on back
        sessionStorage.setItem('bc_results', JSON.stringify({
            perfect: allResults.filter(function (c) { return c.tier === 'perfect'; }),
            substitute: allResults.filter(function (c) { return c.tier === 'substitute'; }),
            close: allResults.filter(function (c) { return c.tier === 'close'; }),
        }));
    }

    function tierLabel(tier) {
        if (tier === 'perfect') return 'Perfect';
        if (tier === 'substitute') return 'With Subs';
        if (tier === 'close') return 'Almost';
        return tier;
    }

    // Filter buttons
    filterBar.addEventListener('click', function (e) {
        var btn = e.target.closest('.filter-btn');
        if (!btn) return;
        var btns = $$('.filter-btn');
        for (var i = 0; i < btns.length; i++) btns[i].classList.remove('active');
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        renderResults();
    });

    sortSelect.addEventListener('change', renderResults);
    spiritFilter.addEventListener('change', renderResults);

    function escHtml(s) {
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }
})();
