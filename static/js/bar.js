/* ===========================
   Bar Cart — My Bar Page
   =========================== */

(function () {
    'use strict';

    var $ = BarCart.$;
    var $$ = BarCart.$$;
    var api = BarCart.api;
    var showToast = BarCart.showToast;

    var container = $('#categories-container');
    var searchInput = $('#ingredient-search');
    var stockCount = $('#stock-count');
    var btnShake = $('#btn-shake');
    var loadingEl = $('#loading-ingredients');
    var stockToggle = $('#stock-toggle');
    var stockChevron = $('#stock-chevron');
    var stockedPanel = $('#stocked-panel');
    var stockedPanelList = $('#stocked-panel-list');
    var panelOpen = false;

    loadIngredients();

    async function loadIngredients() {
        try {
            var result = await api('/api/ingredients');
            var data = result.data;
            renderCategories(data.categories);
            updateStockCount(data.stocked_count);
        } catch (err) {
            container.innerHTML = '<div class="empty-state"><p>Failed to load ingredients.</p></div>';
            showToast(err.message, true);
        }
    }

    function renderCategories(categories) {
        loadingEl.style.display = 'none';
        var html = '';
        for (var i = 0; i < categories.length; i++) {
            var cat = categories[i];
            var stockedInCat = 0;
            for (var j = 0; j < cat.ingredients.length; j++) {
                if (cat.ingredients[j].in_stock) stockedInCat++;
            }
            html += '<div class="category-group" data-cat-id="' + cat.id + '">';
            html += '<div class="category-header">';
            html += '<span class="category-name">' + escHtml(cat.name) + '</span>';
            html += '<div class="category-meta">';
            html += '<span class="category-count">' + stockedInCat + '/' + cat.ingredients.length + '</span>';
            html += '<span class="category-chevron">&#9660;</span>';
            html += '</div></div>';
            html += '<div class="category-items">';
            for (var j = 0; j < cat.ingredients.length; j++) {
                var ing = cat.ingredients[j];
                html += '<div class="ingredient-item' + (ing.in_stock ? ' stocked' : '') + '" data-id="' + ing.id + '" data-name="' + escAttr(normalize(ing.name)) + '">';
                html += '<div class="ingredient-toggle"></div>';
                html += '<span class="ingredient-name">' + escHtml(ing.name) + '</span>';
                html += '</div>';
            }
            html += '</div></div>';
        }
        container.innerHTML = html;

        var headers = $$('.category-header');
        for (var i = 0; i < headers.length; i++) {
            headers[i].addEventListener('click', onCategoryClick);
        }

        var items = $$('.ingredient-item');
        for (var i = 0; i < items.length; i++) {
            items[i].addEventListener('click', onToggle);
        }
    }

    function onCategoryClick(e) {
        var group = e.currentTarget.parentElement;
        var wasOpen = group.classList.contains('open');
        var groups = $$('.category-group');
        for (var i = 0; i < groups.length; i++) {
            groups[i].classList.remove('open');
        }
        if (!wasOpen) {
            group.classList.add('open');
        }
    }

    async function onToggle(e) {
        var item = e.currentTarget;
        var id = parseInt(item.dataset.id);
        var isStocked = item.classList.contains('stocked');
        var newState = !isStocked;

        item.classList.toggle('stocked', newState);

        try {
            var result = await api('/api/bar/stock', 'POST', {
                ingredient_id: id,
                stocked: newState
            });
            updateStockCount(result.data.stocked_count);
            updateCategoryCounts();
            if (panelOpen) renderStockedPanel();
        } catch (err) {
            item.classList.toggle('stocked', isStocked);
            showToast(err.message, true);
        }
    }

    function updateStockCount(count) {
        stockCount.textContent = count;
        btnShake.disabled = count === 0;
    }

    function updateCategoryCounts() {
        var groups = $$('.category-group');
        for (var i = 0; i < groups.length; i++) {
            var items = groups[i].querySelectorAll('.ingredient-item');
            var stocked = 0;
            for (var j = 0; j < items.length; j++) {
                if (items[j].classList.contains('stocked')) stocked++;
            }
            var countEl = groups[i].querySelector('.category-count');
            if (countEl) countEl.textContent = stocked + '/' + items.length;
        }
    }

    // Stocked panel toggle
    stockToggle.addEventListener('click', function () {
        panelOpen = !panelOpen;
        stockedPanel.style.display = panelOpen ? 'block' : 'none';
        stockChevron.style.transform = panelOpen ? 'rotate(180deg)' : '';
        if (panelOpen) renderStockedPanel();
    });

    function renderStockedPanel() {
        var items = $$('.ingredient-item.stocked');
        if (items.length === 0) {
            stockedPanelList.innerHTML = '<p class="stocked-panel-empty">No ingredients stocked yet.</p>';
            return;
        }
        // Gather names sorted alphabetically
        var names = [];
        for (var i = 0; i < items.length; i++) {
            var nameEl = items[i].querySelector('.ingredient-name');
            if (nameEl) names.push(nameEl.textContent);
        }
        names.sort(function (a, b) { return a.toLowerCase().localeCompare(b.toLowerCase()); });

        var html = '';
        for (var i = 0; i < names.length; i++) {
            html += '<a class="stocked-panel-item" href="#" data-ingredient="' + escAttr(names[i]) + '">' + escHtml(names[i]) + '</a>';
        }
        stockedPanelList.innerHTML = html;

        var panelItems = stockedPanelList.querySelectorAll('.stocked-panel-item');
        for (var i = 0; i < panelItems.length; i++) {
            panelItems[i].addEventListener('click', function (e) {
                e.preventDefault();
                var name = e.currentTarget.dataset.ingredient;
                // Set results page state: ingredient chip + perfect filter
                sessionStorage.setItem('bc_ingredients', JSON.stringify([name]));
                sessionStorage.setItem('bc_filter', 'perfect');
                sessionStorage.removeItem('bc_scroll');
                window.location.href = '/results';
            });
        }
    }

    // Strip accents and lowercase for search matching
    function normalize(s) {
        return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    }

    // Search / filter
    searchInput.addEventListener('input', function () {
        var query = normalize(this.value.trim());
        var groups = $$('.category-group');
        for (var i = 0; i < groups.length; i++) {
            var items = groups[i].querySelectorAll('.ingredient-item');
            var anyVisible = false;
            for (var j = 0; j < items.length; j++) {
                var match = !query || items[j].dataset.name.indexOf(query) !== -1;
                items[j].classList.toggle('hidden', !match);
                if (match) anyVisible = true;
            }
            groups[i].classList.toggle('hidden', !anyVisible);
            if (query && anyVisible) {
                groups[i].classList.add('open');
            } else if (!query) {
                groups[i].classList.remove('open');
            }
        }
    });

    // Shake button — full-screen shaker animation + random perfect match
    var isShaking = false;
    var overlay = $('#shake-overlay');
    var shakerUnit = $('#shaker-unit');
    var shakerLid = $('#shaker-lid');
    var shakerResult = $('#shaker-result');

    btnShake.addEventListener('click', function () {
        if (isShaking || btnShake.disabled) return;
        isShaking = true;

        // Pulse the button & start API fetch in parallel
        btnShake.classList.add('shaking');
        var fetchPromise = api('/api/shake');

        // 300ms: show overlay with shaker (lid raised)
        setTimeout(function () {
            btnShake.classList.remove('shaking');
            overlay.classList.add('active');

            // 400ms: lid descends onto body
            setTimeout(function () {
                shakerLid.classList.add('seated');

                // Wait for API result, then shake
                fetchPromise.then(function (result) {
                    var perfect = result.data.perfect || [];

                    if (perfect.length === 0) {
                        resetShake();
                        showToast('No perfect matches — try adding more ingredients!', true);
                        return;
                    }

                    var cocktail = perfect[Math.floor(Math.random() * perfect.length)];

                    // Small pause after lid seats, then shake
                    setTimeout(function () {
                        shakerUnit.classList.add('shaking');

                        // After shake: reveal cocktail name
                        setTimeout(function () {
                            shakerUnit.classList.remove('shaking');
                            shakerUnit.classList.add('reveal');
                            shakerResult.textContent = cocktail.name;
                            shakerResult.classList.add('visible');

                            // Navigate to recipe
                            setTimeout(function () {
                                window.location.href = '/recipe/' + cocktail.id;
                            }, 800);
                        }, 1200);
                    }, 200);

                }).catch(function (err) {
                    resetShake();
                    showToast(err.message || 'Something went wrong', true);
                });
            }, 400);
        }, 300);
    });

    function resetShake() {
        overlay.classList.remove('active');
        shakerUnit.classList.remove('shaking', 'reveal');
        shakerLid.classList.remove('seated');
        shakerResult.classList.remove('visible');
        shakerResult.textContent = '';
        isShaking = false;
    }

    function escHtml(s) {
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    function escAttr(s) {
        return s.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
})();
