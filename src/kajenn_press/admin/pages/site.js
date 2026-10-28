// Preview HTML additions, never part of published pages: slot borders and a script that
// reports clicks on slots and links to the administration with postMessage.
const SLOT_CSS = '<style>[kpress_slot]{outline:1px dashed #1d5fa5;outline-offset:2px;cursor:pointer}</style>';
const PREVIEW_SCRIPT = `
document.addEventListener('click', function (event) {
  var slot = event.target.closest('[kpress_slot]');
  var link = event.target.closest('a[href]');
  if (slot) { event.preventDefault(); parent.postMessage({kind: 'slot', slot: slot.getAttribute('kpress_slot')}, '*'); }
  else if (link) { event.preventDefault(); parent.postMessage({kind: 'link', href: link.getAttribute('href')}, '*'); }
});`;

function previewHtml(html, slots, nonce) {
    const additions = (slots ? SLOT_CSS : '') + `<script nonce="${nonce}">${PREVIEW_SCRIPT}<\/script>`;
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
            if (event.data.kind === 'slot') {
                node.SET('site.assign_page', node.GET('site.page'));
                node.SET('site.assign_slot', event.data.slot);
                void this.openSlot(node, {});
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
            const result = await this.callCommand('page_render', {site_id: this.siteId(node), page_id: page});
            if (result.status !== 'succeeded') {
                node.SET('site.status', result.diagnostics.map(d => d.message).join(' · '));
                return;
            }
            const nonce = document.querySelector('script[nonce]')?.nonce ?? '';
            node.SET('site.preview', previewHtml(result.html, node.GET('site.show_slots'), nonce));
            node.SET('site.status', pages[page].url + ' · ' + pages[page].name);
        } catch (error) { node.SET('site.status', error.message); }
    }
    selectTreeItem(node, {path}) {
        if (!path) return;
        const item = node.GET('site.pages_tree').getNode(path);
        if (!item) return;
        if (item.attr.page) node.SET('site.page', item.attr.page);
        if (item.attr.kind === 'slot') {
            node.SET('site.assign_page', item.attr.page);
            node.SET('site.assign_slot', item.attr.slot);
            node.SET('site.assign_content', item.attr.content);
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
    contentClass(source, item) { return item && item.attr && item.attr.unused ? 'content-unused' : ''; }
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
        node.SET('site.editor_content', content);
        node.SET('site.editor_title', slot + ' · ' + read[content].name);
        node.SET('site.editor_text', read[content].text);
        node.SET('site.plan_json', '');
        node.SET('site.editor_open', true);
    }
    closeEditor(node, _args) { node.SET('site.editor_open', false); }
    async saveContent(node, _args) {
        const site = this.siteId(node), content = node.GET('site.editor_content');
        node.SET('site.busy', true);
        try {
            await this.callCommand('content_save', {site_id: site, key: crypto.randomUUID(), content_id: content,
                text: node.GET('site.editor_text')});
            const plan = await this.callCommand('copies_update_plan', {site_id: site, original_id: content});
            const pages = JSON.parse(node.GET('site.pages_json'));
            node.SET('site.plan_json', JSON.stringify(plan.map(item => ({...item, page_name: pages[item.page_id].name}))));
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
    async createSite(node, _args) {
        const name = node.GET('site.new_name');
        if (!name) { node.SET('site.message', 'Give the site a name.'); return; }
        try {
            const result = await this.callCommand('site_new', {key: crypto.randomUUID(), name});
            window.location.search = '?site=' + result.site_id;
        } catch (error) { node.SET('site.message', error.message); }
    }
}
