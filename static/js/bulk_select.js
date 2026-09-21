/**
 * Generic multi-page-persistent bulk selection helper.
 *
 * Selected row IDs are kept in sessionStorage so they survive pagination
 * (navigating to another page of the same list) but are scoped to the
 * current browser tab/session. Row checkboxes only need a `row-cb` class
 * and a `data-id` attribute; they should NOT have a `name` attribute,
 * since the actual submitted values are injected as hidden inputs built
 * from the full cross-page selection at submit time.
 *
 * @param {Object} options
 * @param {string} options.storageKey - sessionStorage key for this list.
 * @param {string} options.idFieldName - name given to generated hidden inputs.
 * @param {string} options.itemLabel - Arabic noun used in the count label.
 * @param {string} [options.bulkFormId='bulk-form']
 * @param {string} [options.checkAllId='check-all']
 * @param {string} [options.toolbarId='bulk-toolbar']
 * @param {string} [options.countLabelId='bulk-count-label']
 * @returns {{getSelectedIds: function, clear: function, buildHiddenInputs: function}}
 */
function initBulkSelect(options) {
    const {
        storageKey,
        idFieldName,
        itemLabel,
        bulkFormId = 'bulk-form',
        checkAllId = 'check-all',
        toolbarId = 'bulk-toolbar',
        countLabelId = 'bulk-count-label',
    } = options;

    function loadSet() {
        try {
            const raw = sessionStorage.getItem(storageKey);
            return new Set(raw ? JSON.parse(raw) : []);
        } catch (e) {
            return new Set();
        }
    }

    function saveSet(set) {
        sessionStorage.setItem(storageKey, JSON.stringify(Array.from(set)));
    }

    const selected = loadSet();

    const checkAll = document.getElementById(checkAllId);
    const toolbar = document.getElementById(toolbarId);
    const countLabel = document.getElementById(countLabelId);
    const bulkForm = document.getElementById(bulkFormId);

    function rowCbs() {
        return document.querySelectorAll('.row-cb');
    }

    function updateToolbar() {
        const n = selected.size;
        if (toolbar) {
            if (n > 0) {
                toolbar.classList.remove('d-none');
                toolbar.classList.add('d-flex');
            } else {
                toolbar.classList.add('d-none');
                toolbar.classList.remove('d-flex');
            }
        }
        if (countLabel) {
            countLabel.textContent = n > 0 ? ('تم تحديد ' + n + ' ' + itemLabel) : '';
        }
        const all = Array.from(rowCbs());
        const checkedOnPage = all.filter(cb => selected.has(cb.dataset.id));
        if (checkAll) {
            checkAll.indeterminate = checkedOnPage.length > 0 && checkedOnPage.length < all.length;
            checkAll.checked = all.length > 0 && checkedOnPage.length === all.length;
        }
    }

    function applyPageState() {
        rowCbs().forEach(cb => { cb.checked = selected.has(cb.dataset.id); });
        updateToolbar();
    }

    rowCbs().forEach(cb => cb.addEventListener('change', function () {
        if (this.checked) selected.add(this.dataset.id);
        else selected.delete(this.dataset.id);
        saveSet(selected);
        updateToolbar();
    }));

    if (checkAll) {
        checkAll.addEventListener('change', function () {
            rowCbs().forEach(cb => {
                cb.checked = this.checked;
                if (this.checked) selected.add(cb.dataset.id);
                else selected.delete(cb.dataset.id);
            });
            saveSet(selected);
            updateToolbar();
        });
    }

    function buildHiddenInputs(form) {
        form.querySelectorAll('input.bulk-hidden-id').forEach(el => el.remove());
        selected.forEach(id => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = idFieldName;
            input.className = 'bulk-hidden-id';
            input.value = id;
            form.appendChild(input);
        });
    }

    function clear() {
        selected.clear();
        saveSet(selected);
        applyPageState();
    }

    applyPageState();

    return {
        getSelectedIds: () => Array.from(selected),
        clear,
        buildHiddenInputs: () => buildHiddenInputs(bulkForm),
    };
}
