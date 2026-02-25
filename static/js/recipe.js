/* ===========================
   Bar Cart — Recipe Page
   =========================== */

(function () {
    'use strict';

    var $ = BarCart.$;
    var api = BarCart.api;
    var showToast = BarCart.showToast;

    var container = $('#recipe-container');
    var loadingEl = $('#loading-recipe');
    var cocktailId = window.COCKTAIL_ID;
    var currentAvg = 0;
    var ratingHistory = [];
    var pendingScore = null;

    loadRecipe();

    async function loadRecipe() {
        try {
            var result = await api('/api/recipe/' + cocktailId);
            var data = result.data;
            currentAvg = data.avg_rating || 0;
            ratingHistory = data.ratings || [];
            renderRecipe(data);
        } catch (err) {
            loadingEl.style.display = 'none';
            container.innerHTML = '<div class="empty-state"><p>Recipe not found.</p></div>';
            showToast(err.message, true);
        }
    }

    function renderRecipe(data) {
        loadingEl.style.display = 'none';

        var html = '<div class="recipe-header">';
        html += '<h1 class="recipe-name">' + escHtml(data.name) + '</h1>';
        if (data.primary_spirit) {
            html += '<div class="recipe-spirit">' + escHtml(data.primary_spirit) + '</div>';
        }
        html += '</div>';

        // Ingredients
        html += '<div class="recipe-section"><h2>Ingredients</h2>';
        html += '<ul class="ingredient-list">';
        for (var i = 0; i < data.ingredients.length; i++) {
            var ing = data.ingredients[i];
            var qty = '';
            if (ing.quantity) qty += ing.quantity;
            if (ing.unit) qty += (qty ? ' ' : '') + ing.unit;
            html += '<li>';
            html += '<span class="ing-status-dot ' + ing.status + '"></span>';
            html += '<span class="ing-qty">' + escHtml(qty) + '</span>';
            html += '<span class="ing-name ' + ing.status + '">' + escHtml(ing.name) + '</span>';
            html += '</li>';
        }
        html += '</ul></div>';

        // Instructions
        if (data.instructions) {
            html += '<div class="recipe-section"><h2>Instructions</h2>';
            html += '<div class="instructions-text">' + escHtml(data.instructions) + '</div>';
            html += '</div>';
        }

        // Rating
        html += '<div class="recipe-section"><h2>Rating</h2>';
        html += '<div class="rating-stars" id="rating-stars">';
        var filled = Math.round(currentAvg);
        for (var i = 1; i <= 5; i++) {
            var cls = i <= filled ? ' filled' : '';
            html += '<button class="rating-star' + cls + '" data-score="' + i + '">&#127820;</button>';
        }
        html += '</div>';
        html += '<div class="rating-comment-form" id="rating-comment-form" style="display:none">';
        html += '<input type="text" id="rating-comment-input" placeholder="Add a comment (optional)" maxlength="200">';
        html += '<button class="btn btn-primary btn-small" id="btn-save-rating">Save</button>';
        html += '</div>';
        html += renderComposite();
        html += '<div id="rating-history">';
        for (var i = 0; i < ratingHistory.length; i++) {
            html += renderRatingEntry(ratingHistory[i]);
        }
        html += '</div></div>';

        // Notes
        html += '<div class="recipe-section"><h2>Notes</h2>';
        html += '<div class="note-form">';
        html += '<textarea id="note-input" placeholder="Add a note..."></textarea>';
        html += '<button class="btn btn-primary btn-small" id="btn-add-note">Add</button>';
        html += '</div>';
        html += '<div id="notes-list">';
        for (var i = 0; i < data.notes.length; i++) {
            html += renderNote(data.notes[i]);
        }
        html += '</div></div>';

        // Source
        if (data.source_url) {
            html += '<div class="recipe-section">';
            html += '<a href="' + escAttr(data.source_url) + '" class="source-link" target="_blank" rel="noopener">';
            html += '&#8594; View on Kindred Cocktails</a>';
            html += '</div>';
        }

        container.innerHTML = html;

        // Attach event handlers
        attachRatingHandlers();
        attachNoteHandlers();
        attachRatingDeleteHandlers();
    }

    function renderComposite() {
        if (!currentAvg) return '<div class="rating-composite" id="rating-composite"></div>';
        return '<div class="rating-composite" id="rating-composite">' +
            currentAvg + ' avg from ' + ratingHistory.length + ' rating' + (ratingHistory.length !== 1 ? 's' : '') +
            '</div>';
    }

    function renderRatingEntry(entry) {
        var dateStr = entry.date ? new Date(entry.date.replace(' ', 'T')).toLocaleDateString() : 'Just now';
        var stars = '';
        for (var i = 0; i < entry.score; i++) stars += '&#127820;';
        var html = '<div class="rating-entry" data-rating-id="' + entry.id + '">' +
            '<div class="rating-entry-main">' +
            '<span class="rating-entry-score">' + stars + '</span>' +
            '<span class="rating-entry-date">' + dateStr + '</span>' +
            '<button class="rating-entry-delete" data-rating-id="' + entry.id + '">Delete</button>' +
            '</div>';
        if (entry.comment) {
            html += '<div class="rating-entry-comment">' + escHtml(entry.comment) + '</div>';
        }
        html += '</div>';
        return html;
    }

    function updateRatingDisplay(data) {
        currentAvg = data.avg_rating || 0;
        ratingHistory = data.ratings || [];

        // Update stars
        var filled = Math.round(currentAvg);
        var stars = container.querySelectorAll('.rating-star');
        for (var i = 0; i < stars.length; i++) {
            var s = parseInt(stars[i].dataset.score);
            stars[i].classList.toggle('filled', s <= filled);
        }

        // Update composite text
        var comp = $('#rating-composite');
        if (comp) {
            comp.innerHTML = currentAvg ?
                currentAvg + ' avg from ' + ratingHistory.length + ' rating' + (ratingHistory.length !== 1 ? 's' : '') :
                '';
        }

        // Update history
        var histEl = $('#rating-history');
        if (histEl) {
            var html = '';
            for (var i = 0; i < ratingHistory.length; i++) {
                html += renderRatingEntry(ratingHistory[i]);
            }
            histEl.innerHTML = html;
            attachRatingDeleteHandlers();
        }
    }

    function renderNote(note) {
        var dateStr = note.date ? new Date(note.date.replace(' ', 'T')).toLocaleDateString() : 'Just now';
        var html = '<div class="note-item" data-note-id="' + note.id + '">';
        html += '<div class="note-text">' + escHtml(note.text) + '</div>';
        html += '<div class="note-footer">';
        html += '<span class="note-date">' + dateStr + '</span>';
        html += '<button class="note-delete" data-note-id="' + note.id + '">Delete</button>';
        html += '</div></div>';
        return html;
    }

    function attachRatingHandlers() {
        var stars = container.querySelectorAll('.rating-star');
        for (var i = 0; i < stars.length; i++) {
            stars[i].addEventListener('click', onRate);
            stars[i].addEventListener('mouseenter', onStarHover);
            stars[i].addEventListener('mouseleave', onStarLeave);
        }
        var saveBtn = $('#btn-save-rating');
        if (saveBtn) saveBtn.addEventListener('click', submitRating);
        var commentInput = $('#rating-comment-input');
        if (commentInput) {
            commentInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') submitRating();
            });
        }
    }

    function attachRatingDeleteHandlers() {
        var btns = container.querySelectorAll('.rating-entry-delete');
        for (var i = 0; i < btns.length; i++) {
            btns[i].onclick = onDeleteRating;
        }
    }

    function onStarHover(e) {
        var score = parseInt(e.target.dataset.score);
        var stars = container.querySelectorAll('.rating-star');
        for (var i = 0; i < stars.length; i++) {
            var s = parseInt(stars[i].dataset.score);
            stars[i].classList.toggle('hovered', s <= score);
        }
    }

    function onStarLeave() {
        var stars = container.querySelectorAll('.rating-star');
        for (var i = 0; i < stars.length; i++) {
            stars[i].classList.remove('hovered');
        }
    }

    function onRate(e) {
        var score = parseInt(e.target.dataset.score);
        var form = $('#rating-comment-form');
        // Quick-rate: clicking same star twice submits immediately
        if (pendingScore === score) {
            submitRating();
            return;
        }
        pendingScore = score;
        // Highlight selected stars
        var stars = container.querySelectorAll('.rating-star');
        for (var i = 0; i < stars.length; i++) {
            var s = parseInt(stars[i].dataset.score);
            stars[i].classList.toggle('filled', s <= score);
        }
        if (form) {
            form.style.display = 'flex';
            var input = $('#rating-comment-input');
            if (input) input.focus();
        }
    }

    async function submitRating() {
        if (!pendingScore) return;
        var commentInput = $('#rating-comment-input');
        var comment = commentInput ? commentInput.value.trim() : '';
        var score = pendingScore;
        pendingScore = null;
        try {
            var body = { score: score };
            if (comment) body.comment = comment;
            var result = await api('/api/recipe/' + cocktailId + '/rate', 'POST', body);
            updateRatingDisplay(result.data);
            showToast('Rated ' + score + '/5');
            var form = $('#rating-comment-form');
            if (form) form.style.display = 'none';
            if (commentInput) commentInput.value = '';
        } catch (err) {
            showToast(err.message, true);
        }
    }

    async function onDeleteRating(e) {
        var ratingId = e.target.dataset.ratingId;
        try {
            var result = await api('/api/recipe/' + cocktailId + '/rate/' + ratingId, 'DELETE');
            updateRatingDisplay(result.data);
            showToast('Rating deleted');
        } catch (err) {
            showToast(err.message, true);
        }
    }

    function attachNoteHandlers() {
        var btnAdd = $('#btn-add-note');
        var noteInput = $('#note-input');
        var notesList = $('#notes-list');

        btnAdd.addEventListener('click', async function () {
            var text = noteInput.value.trim();
            if (!text) return;

            try {
                var result = await api('/api/recipe/' + cocktailId + '/note', 'POST', { text: text });
                noteInput.value = '';
                notesList.insertAdjacentHTML('afterbegin', renderNote(result.data));
                attachDeleteHandlers();
                showToast('Note added');
            } catch (err) {
                showToast(err.message, true);
            }
        });

        attachDeleteHandlers();
    }

    function attachDeleteHandlers() {
        var btns = container.querySelectorAll('.note-delete');
        for (var i = 0; i < btns.length; i++) {
            btns[i].onclick = onDeleteNote;
        }
    }

    async function onDeleteNote(e) {
        var noteId = e.target.dataset.noteId;
        try {
            await api('/api/recipe/' + cocktailId + '/note/' + noteId, 'DELETE');
            var item = container.querySelector('.note-item[data-note-id="' + noteId + '"]');
            if (item) item.remove();
            showToast('Note deleted');
        } catch (err) {
            showToast(err.message, true);
        }
    }

    function escHtml(s) {
        if (!s) return '';
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    function escAttr(s) {
        if (!s) return '';
        return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
})();
