// Preview HTML additions, never part of published pages: slot borders, the selection with
// its label and pen, and a script that reports selections, edits and links with postMessage.
const SLOT_CSS = '<style>[kpress_slot]{outline:1px dashed #1d5fa5;outline-offset:2px;cursor:pointer}[kpress_fallback]{outline:1px dashed #e05a5a;background:#fdecec}</style>';
const SELECTION_CSS = '<style>[kpress_chrome]{position:absolute;z-index:2147483647;pointer-events:none;border:2px solid #2f6fde;border-radius:6px;box-sizing:border-box}'
    + '[kpress_chrome] .kp-label{position:absolute;top:-11px;left:10px;background:#2f6fde;color:#fff;font:600 11px/1.6 system-ui,sans-serif;padding:0 7px;border-radius:4px;white-space:nowrap}'
    + '[kpress_chrome] .kp-pen{position:absolute;top:-15px;right:10px;width:30px;height:30px;border-radius:50%;border:0;background:#2f6fde;color:#fff;cursor:pointer;pointer-events:auto;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(0,0,0,.25)}'
    + '[kpress_chrome] .kp-pen svg{width:15px;height:15px}</style>';
const PEN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>';
const PREVIEW_SCRIPT = `
(function () {
  var selected = null, chrome = null;
  function report(kind, slot) { parent.postMessage({kind: kind, slot: slot.getAttribute('kpress_slot')}, '*'); }
  function place() {
    if (!selected) return;
    var box = selected.getBoundingClientRect();
    chrome.style.top = (box.top + window.scrollY - 4) + 'px';
    chrome.style.left = (box.left + window.scrollX - 4) + 'px';
    chrome.style.width = (box.width + 8) + 'px';
    chrome.style.height = (box.height + 8) + 'px';
  }
  function select(slot) {
    if (!chrome) {
      chrome = document.createElement('div');
      chrome.setAttribute('kpress_chrome', '');
      chrome.innerHTML = '<span class="kp-label"></span><button type="button" class="kp-pen" title="Edit">PEN_ICON</button>';
      chrome.querySelector('.kp-pen').addEventListener('click', function (event) {
        event.preventDefault(); event.stopPropagation();
        if (selected) report('edit', selected);
      });
      document.body.appendChild(chrome);
    }
    selected = slot;
    chrome.querySelector('.kp-label').textContent = LABELS[slot.getAttribute('kpress_slot')] || slot.getAttribute('kpress_slot');
    place();
  }
  window.addEventListener('resize', place);
  document.addEventListener('click', function (event) {
    if (event.target.closest('[kpress_chrome]')) return;
    var link = event.target.closest('a[href]');
    var slot = event.target.closest('[kpress_slot]');
    // A link is followed even inside a block, as a visitor would (d-block-editing).
    if (link) { event.preventDefault(); parent.postMessage({kind: 'link', href: link.getAttribute('href')}, '*'); }
    else if (slot) { event.preventDefault(); select(slot); report('select', slot); }
  });
  document.addEventListener('dblclick', function (event) {
    var slot = event.target.closest('[kpress_slot]');
    if (slot && !event.target.closest('a[href]')) { event.preventDefault(); select(slot); report('edit', slot); }
  });
})();`;

function previewHtml(html, slots, nonce, labels) {
    // Labels go into a script: `<` is escaped so no text can close it.
    // Function replacements: a `$` in a content name stays literal.
    const script = PREVIEW_SCRIPT.replace('PEN_ICON', () => PEN)
        .replace('LABELS[', () => '(' + JSON.stringify(labels).replace(/</g, '\\u003c') + ')[');
    const additions = (slots ? SLOT_CSS : '') + SELECTION_CSS + `<script nonce="${nonce}">${script}<\/script>`;
    return html.includes('</body>') ? html.replace('</body>', additions + '</body>') : html + additions;
}

export class Logic {
    async callCommand(operation, arguments_) {
        const reply = await this.page.rpc.call('data', 'command', {operation, arguments: arguments_});
        if (!reply.ok) throw new Error(reply.error.message);
        return reply.result;
    }
    siteId(node) { return node.GET('site.id'); }
    refresh(node) { node.SET('site.version', node.GET('site.version') + 1); }
    initialize(node, _args) {
        const listener = event => {
            if (!event.data || typeof event.data !== 'object') return;
            if (event.data.kind === 'select' || event.data.kind === 'edit') {
                const page = node.GET('site.page');
                const path = this.slotPath(node.GET('site.pages_tree'), page, event.data.slot);
                this.fromPreview = true;
                if (path) node.SET('site.selected_path', path);
                this.fromPreview = false;
                node.SET('site.assign_page', page);
                node.SET('site.assign_slot', event.data.slot);
                if (event.data.kind === 'edit') void this.openSlot(node, {});
            } else if (event.data.kind === 'link') {
                const pages = JSON.parse(node.GET('site.pages_json'));
                const target = Object.keys(pages).find(id => pages[id].url === event.data.href);
                if (target) node.SET('site.page', target);
                else node.SET('site.status', 'Link outside the site: ' + event.data.href);
            }
        };
        window.addEventListener('message', listener);
        this.page.src.renderer.onDispose(node.parentNode, () => window.removeEventListener('message', listener));
        if (!node.GET('site.editing') && !node.GET('site.holder')) void this.takeSite(node, {force: false});
    }
    async takeSite(node, {force = true} = {}) {
        try {
            await this.callCommand('site_open', {site_id: this.siteId(node), force});
            this.refresh(node);
        } catch (error) { node.SET('site.message', error.message); }
    }
    async renderPage(node, _args) {
        const page = node.GET('site.page');
        if (!page) { node.SET('site.status', 'This site has no page yet.'); return; }
        const pages = JSON.parse(node.GET('site.pages_json'));
        node.SET('site.status', 'Rendering ' + pages[page].url + ' …');
        try {
            const result = await this.callCommand('page_render', {site_id: this.siteId(node), page_id: page,
                language: node.GET('site.language')});
            if (result.status !== 'succeeded') {
                node.SET('site.status', result.diagnostics.map(d => d.message).join(' · '));
                return;
            }
            const nonce = document.querySelector('script[nonce]')?.nonce ?? '';
            node.SET('site.preview', previewHtml(result.html, node.GET('site.show_slots'), nonce,
                this.slotLabels(node, page)));
            node.SET('site.status', pages[page].url + ' · ' + pages[page].name);
        } catch (error) { node.SET('site.status', error.message); }
    }
    slotPath(bag, page, slot, prefix = '') {
        // The Pages tree nests pages in folders: find the slot node wherever its page is.
        for (const item of bag.getNodes()) {
            const path = prefix ? prefix + '.' + item.label : item.label;
            if (item.attr.kind === 'slot' && item.attr.page === page && item.attr.slot === slot) return path;
            if (item.value && typeof item.value.getNodes === 'function') {
                const found = this.slotPath(item.value, page, slot, path);
                if (found) return found;
            }
        }
        return null;
    }
    slotLabels(node, page) {
        // "slot · content" for each slot of the page, shown on the selection.
        const contents = JSON.parse(node.GET('site.contents_json')), labels = {};
        const tree = node.GET('site.pages_tree');
        const walk = bag => { for (const item of bag.getNodes()) {
            if (item.attr.kind === 'slot' && item.attr.page === page) {
                labels[item.attr.slot] = item.attr.slot + (item.attr.content ? ' · ' + contents[item.attr.content].name : ' · empty');
            }
            if (item.value && typeof item.value.getNodes === 'function') walk(item.value);
        } };
        walk(tree);
        return labels;
    }
    selectTreeItem(node, {path}) {
        if (!path) return;
        const item = node.GET('site.pages_tree').getNode(path);
        if (!item) return;
        // Setting the same page renders it again and would drop the selection in the preview.
        if (item.attr.page && item.attr.page !== node.GET('site.page')) node.SET('site.page', item.attr.page);
        if (item.attr.kind === 'slot') {
            node.SET('site.assign_page', item.attr.page);
            node.SET('site.assign_slot', item.attr.slot);
            node.SET('site.assign_content', item.attr.content);
            // A slot chosen in the tree opens like the pen; one chosen in the preview only selects.
            if (!this.fromPreview && item.attr.content) void this.openSlot(node, {});
        }
    }
    preparePage(source, {dragValues, item}) {
        if (item.attr.kind === 'page' || item.attr.kind === 'folder') {
            dragValues['app/kpress-page'] = {item: item.attr.item ?? item.attr.page};
        }
    }
    prepareContent(source, {dragValues, item}) {
        dragValues['app/kpress-content'] = {content: item.attr.content};
    }
    acceptDrop(source, {item}) { return item.attr.kind === 'slot' || item.attr.kind === 'folder'; }
    contentClass(source, {item}) { return item.attr.unused ? 'content-unused' : ''; }
    async dropOnTree(source, {dropValues, item}) {
        const site = this.siteId(source);
        try {
            if (dropValues['app/kpress-content'] && item.attr.kind === 'slot') {
                await this.callCommand('slot_assign', {site_id: site, key: crypto.randomUUID(), page_id: item.attr.page,
                    slot: item.attr.slot, content_id: dropValues['app/kpress-content'].content});
            } else if (dropValues['app/kpress-page'] && item.attr.kind === 'folder') {
                await this.callCommand('tree_move', {site_id: site, key: crypto.randomUUID(),
                    item_id: dropValues['app/kpress-page'].item, parent: item.attr.item});
            } else return;
            this.refresh(source);
        } catch (error) { source.SET('site.message', error.message); }
    }
    async assignChosen(node, _args) {
        if (!node.GET('site.assign_content')) { node.SET('site.message', 'Choose a content first.'); return; }
        try {
            await this.callCommand('slot_assign', {site_id: this.siteId(node), key: crypto.randomUUID(),
                page_id: node.GET('site.assign_page'), slot: node.GET('site.assign_slot'),
                content_id: node.GET('site.assign_content')});
            this.refresh(node);
        } catch (error) { node.SET('site.message', error.message); }
    }
    async openSlot(node, _args) {
        const read = JSON.parse(node.GET('site.contents_json'));
        const page = node.GET('site.assign_page'), slot = node.GET('site.assign_slot');
        const item = node.GET('site.pages_tree').getNode(page + '.slot_' + slot);
        const content = item ? item.attr.content : '';
        if (!content) { node.SET('site.message', 'Slot ' + slot + ' is empty: assign a content first.'); return; }
        const language = node.GET('site.language'), main = language === node.GET('site.main_language');
        const translation = main ? null : read[content].translations[language];
        node.SET('site.editor_content', content);
        node.SET('site.editor_title', slot + ' · ' + read[content].name + (main ? '' : ' · ' + language.toUpperCase()));
        node.SET('site.editor_main', main ? '' : read[content].text);
        node.SET('site.editor_text', main ? read[content].text : (translation.text ?? ''));
        node.SET('site.editor_original', node.GET('site.editor_text'));
        node.SET('site.editor_state', main ? '' : translation.state);
        node.SET('site.editor_note', main || translation.state === 'done' ? '' : translation.state.replace('_', ' '));
        node.SET('site.plan_json', '');
        node.SET('site.editor_open', true);
    }
    closeEditor(node, _args) { node.SET('site.editor_open', false); }
    toggleSource(node, _event) { node.SET('site.editor_source', !node.GET('site.editor_source')); }
    dragWindow(_node, event) {
        // Full height always: the window moves sideways only, inside the stage.
        if (event.target.closest('button')) return;
        const win = event.currentTarget.closest('.block-window'), stage = win.parentElement;
        const start = event.clientX - win.offsetLeft;
        const move = m => {
            const left = Math.max(0, Math.min(m.clientX - start, stage.clientWidth - win.offsetWidth));
            win.style.right = 'auto';
            win.style.left = left + 'px';
        };
        document.addEventListener('mousemove', move);
        document.addEventListener('mouseup', () => document.removeEventListener('mousemove', move), {once: true});
    }
    async confirmTranslation(node, _args) {
        try {
            await this.callCommand('translation_confirm', {site_id: this.siteId(node), key: crypto.randomUUID(),
                translation: 'content_' + node.GET('site.editor_content'), language: node.GET('site.language')});
            node.SET('site.editor_state', 'done');
            node.SET('site.editor_note', '');
            this.refresh(node);
        } catch (error) { node.SET('site.message', error.message); }
    }
    async saveContent(node, _args) {
        const site = this.siteId(node), content = node.GET('site.editor_content');
        node.SET('site.busy', true);
        try {
            const language = node.GET('site.language');
            if (language === node.GET('site.main_language')) {
                await this.callCommand('content_save', {site_id: site, key: crypto.randomUUID(), content_id: content,
                    text: node.GET('site.editor_text')});
            } else {
                await this.callCommand('content_translate', {site_id: site, key: crypto.randomUUID(),
                    content_id: content, language, text: node.GET('site.editor_text')});
                node.SET('site.editor_state', 'done');
                node.SET('site.editor_note', '');
            }
            const plan = await this.callCommand('copies_update_plan', {site_id: site, original_id: content});
            const pages = JSON.parse(node.GET('site.pages_json'));
            node.SET('site.plan_json', JSON.stringify(plan.map(item => ({...item, page_name: pages[item.page_id].name}))));
            node.SET('site.editor_original', node.GET('site.editor_text'));
            // Without copies to update, the window closes and the preview shows the change.
            if (!plan.length) { node.SET('site.editor_open', false); this.refresh(node); }
        } catch (error) { node.SET('site.message', error.message); }
        node.SET('site.busy', false);
    }
    async applyUpdate(node, _args) {
        const plan = JSON.parse(node.GET('site.plan_json') || '[]');
        const selected = plan.filter((_item, index) => node.GET('site.plan.i' + index)).map(item => [item.page_id, item.path]);
        try {
            await this.callCommand('copies_update', {site_id: this.siteId(node), key: crypto.randomUUID(),
                original_id: node.GET('site.editor_content'), selected});
            node.SET('site.plan_json', '');
            node.SET('site.editor_open', false);
            this.refresh(node);
        } catch (error) { node.SET('site.message', error.message); }
    }
    async save(node, _args) {
        node.SET('site.busy', true);
        try {
            const result = await this.callCommand('site_save', {site_id: this.siteId(node)});
            node.SET('site.message', 'Saved as version ' + result.version_id.slice(0, 8));
        } catch (error) { node.SET('site.message', error.message); }
        node.SET('site.busy', false);
    }
    async addPage(node, _args) {
        try {
            await this.callCommand('page_add', {site_id: this.siteId(node), key: crypto.randomUUID(),
                name: 'New page', template_id: node.GET('site.template_id')});
            this.refresh(node);
        } catch (error) { node.SET('site.message', error.message); }
    }
    async addFolder(node, _args) {
        try {
            await this.callCommand('folder_add', {site_id: this.siteId(node), key: crypto.randomUUID(), name: 'New folder'});
            this.refresh(node);
        } catch (error) { node.SET('site.message', error.message); }
    }
    async addContent(node, _args) {
        const name = node.GET('site.new_content_name');
        if (!name) { node.SET('site.message', 'Give the content a name.'); return; }
        try {
            await this.callCommand('content_add', {site_id: this.siteId(node), key: crypto.randomUUID(), name,
                format: 'html', text: '<p></p>'});
            this.refresh(node);
        } catch (error) { node.SET('site.message', error.message); }
    }
    seoClass(source, {item}) { return 'seo-state-' + item.attr.state; }
    async saveSeo(node, _args) {
        const site = this.siteId(node), initial = JSON.parse(node.GET('site.seo_initial'));
        const fields = {};
        for (const name of Object.keys(initial.fields)) {
            const value = node.GET('site.seo.' + name) ?? '';
            if (value !== initial.fields[name]) fields[name] = value;
        }
        const language = initial.language;
        node.SET('site.busy', true);
        try {
            const languages = node.GET('site.seo.languages') ?? '';
            if (!language && languages !== initial.languages) {
                await this.callCommand('site_languages_set', {site_id: site, key: crypto.randomUUID(),
                    languages: languages.split(',').map(code => code.trim().toLowerCase()).filter(Boolean)});
            }
            if (Object.keys(fields).length) {
                await this.callCommand('page_seo_set', {site_id: site, key: crypto.randomUUID(),
                    page_id: initial.page, fields, language});
            }
            const url = node.GET('site.seo.url');
            if (url !== initial.url) {
                await this.callCommand('page_url_set', {site_id: site, key: crypto.randomUUID(),
                    page_id: initial.page, url, language});
            }
            for (const [index, image] of initial.images.entries()) {
                const alt = node.GET('site.seo.alt.i' + index) ?? '';
                if (alt && alt !== image.alt) {
                    await this.callCommand('page_alt_set', {site_id: site, key: crypto.randomUUID(),
                        page_id: initial.page, image: image.image, alt});
                }
            }
            node.SET('site.seo_version', node.GET('site.seo_version') + 1);
            if (!language && languages !== initial.languages) this.refresh(node);
        } catch (error) { node.SET('site.seo_message', error.message); }
        node.SET('site.busy', false);
    }
    toggleHelp(node, _args) { node.SET('site.help_open', !node.GET('site.help_open')); }
    async helpSend(node, _args) {
        const text = (node.GET('site.help_text') || '').trim();
        if (!text) { node.SET('site.help_message', 'Write a message first.'); return; }
        await this.helpTurn(node, text);
    }
    async helpPick(node, _event) { await this.helpTurn(node, node.getAttr('title')); }
    async helpTurn(node, text) {
        node.SET('site.help_busy', true);
        node.SET('site.help_message', 'Help me is working…');
        try {
            const reply = await this.page.rpc.call('data', 'help_call', {call: 'send',
                arguments: {site_id: this.siteId(node), text, chat_id: node.GET('site.help_chat') || null}});
            if (!reply.ok) throw new Error(reply.error.message);
            node.SET('site.help_text', '');
            node.SET('site.help_message', '');
            node.SET('site.help_chat', reply.result.chat_id);
            node.SET('site.help_version', node.GET('site.help_version') + 1);
            this.refresh(node);
        } catch (error) { node.SET('site.help_message', error.message); }
        node.SET('site.help_busy', false);
    }
    showPublish(node, _args) { node.SET('site.pub_panel', 'publish'); }
    showRollback(node, _args) { node.SET('site.pub_panel', 'rollback'); }
    showPrivate(node, _args) { node.SET('site.pub_panel', 'private'); }
    closePanel(node, _args) { node.SET('site.pub_panel', ''); }
    showGoLive(node, _args) { node.SET('site.pub_panel', 'golive'); }
    async goLiveSave(node, _args) {
        const site = this.siteId(node), domain = (node.GET('site.gl_domain') || '').trim().toLowerCase();
        if (!domain) { node.SET('site.gl_result', 'Write the domain first.'); return; }
        const address = 'https://' + (node.GET('site.gl_canonical') === 'www' ? 'www.' + domain : domain);
        try {
            await this.callCommand('page_seo_set', {site_id: site, key: crypto.randomUUID(),
                page_id: node.GET('site.gl_root'), fields: {origin: address}});
            await this.callCommand('site_server_set', {site_id: site, key: crypto.randomUUID(),
                server: node.GET('site.gl_server'), alias: true});
            node.SET('site.gl_result', 'Saved: ' + address);
            node.SET('site.gl_dns_version', node.GET('site.gl_dns_version') + 1);
        } catch (error) { node.SET('site.gl_result', error.message); }
    }
    goLiveCheck(node, _args) { node.SET('site.gl_dns_version', node.GET('site.gl_dns_version') + 1); }
    async goLiveRun(node, _args) {
        node.SET('site.busy', true);
        node.SET('site.gl_result', 'Publishing and asking the server…');
        try {
            const result = await this.callCommand('site_go_live', {site_id: this.siteId(node), key: crypto.randomUUID()});
            const lines = result.steps.map(s => (s.ok ? '✓ ' : '✗ ') + s.step + (s.ok ? '' : ': ' + (typeof s.detail === 'string' ? s.detail : 'see the DNS records')));
            node.SET('site.gl_result', lines.join(' · ') + (result.ok ? ' · online at ' + result.address : ''));
            if (result.ok) node.SET('site.pub_version', node.GET('site.pub_version') + 1);
        } catch (error) { node.SET('site.gl_result', error.message); }
        node.SET('site.busy', false);
    }
    async publishCommand(node, operation, arguments_, done) {
        node.SET('site.busy', true);
        try {
            const result = await this.callCommand(operation, {site_id: this.siteId(node), key: crypto.randomUUID(), ...arguments_});
            node.SET('site.pub_panel', '');
            node.SET('site.pub_version', node.GET('site.pub_version') + 1);
            node.SET('site.pub_message', done(result));
        } catch (error) { node.SET('site.pub_message', error.message); }
        node.SET('site.busy', false);
    }
    async publishSelected(node, _args) {
        const pages = JSON.parse(node.GET('site.pub_plan'));
        const selected = pages.filter((_page, index) => node.GET('site.pub_sel.i' + index));
        await this.publishCommand(node, 'publish', {selected}, result =>
            `Published ${result.published.length} page(s)` + (result.failed.length ? `, ${result.failed.length} failed` : ''));
    }
    async rollbackChosen(node, _args) {
        const version = node.GET('site.pub_rollback_version'), target = node.GET('site.pub_target');
        if (!version) { node.SET('site.pub_message', 'Choose a version first.'); return; }
        if (target === 'site') await this.publishCommand(node, 'site_rollback', {version_id: version}, () => 'Site rolled back');
        else await this.publishCommand(node, 'page_rollback', {page_id: target, version_id: version}, () => 'Page rolled back');
    }
    async toggleMaintenance(node, _args) {
        const on = !node.GET('site.pub_maintenance');
        await this.publishCommand(node, 'maintenance_set', {on}, () => on ? 'Maintenance on' : 'Maintenance off');
    }
    async makePublic(node, _args) { await this.publishCommand(node, 'site_visibility_set', {state: 'public'}, () => 'The site is public'); }
    async makePrivate(node, _args) { await this.publishCommand(node, 'site_visibility_set', {state: 'private'}, () => 'The site is private'); }
    async createPrivateLink(node, _args) {
        try {
            const result = await this.callCommand('private_link', {site_id: this.siteId(node), hours: Number(node.GET('site.pub_hours'))});
            node.SET('site.pub_link', result.url);
            return result.url;
        } catch (error) { node.SET('site.pub_message', error.message); }
    }
    async copyPrivateLink(node, _args) {
        const link = node.GET('site.pub_link');
        if (!link) { node.SET('site.pub_message', 'Create a link first.'); return; }
        await navigator.clipboard.writeText(link);
        node.SET('site.pub_message', 'Private link copied');
    }
    async openPrivate(node, _args) {
        const link = node.GET('site.pub_link') || await this.createPrivateLink(node, {});
        if (link) window.open(link, '_blank', 'noopener');
    }
    async createSite(node, _args) {
        const name = node.GET('site.new_name');
        if (!name) { node.SET('site.message', 'Give the site a name.'); return; }
        try {
            const result = await this.callCommand('site_new', {key: crypto.randomUUID(), name});
            window.location.search = '?site=' + result.site_id;
        } catch (error) { node.SET('site.message', error.message); }
    }
}
