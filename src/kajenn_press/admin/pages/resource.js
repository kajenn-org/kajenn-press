function keys(node, path) { return (node.GET(path) || '').split(',').filter(Boolean); }
function blocks(node) {
    const declared = {};
    for (const key of keys(node, 'draft.row_keys')) {
        const row = 'draft.block_rows.' + key;
        declared[node.GET(row + '.name')] = {format: node.GET(row + '.format'), required: !!node.GET(row + '.required')};
    }
    return declared;
}
function dependencies(node) {
    const chosen = keys(node, 'draft.dep_keys').filter(key => node.GET(`draft.deps.${key}.on`))
        .map(key => node.GET(`draft.deps.${key}.revision`));
    return [...JSON.parse(node.GET('res.other_deps') || '[]'), ...chosen];
}
function snapshot(node) {
    const kind = node.GET('res.kind');
    if (kind === 'media') {
        return {name: node.GET('draft.name'), data_base64: node.GET('draft.data_base64'),
            mime_type: node.GET('res.mime_type')};
    }
    const value = {name: node.GET('draft.name'), source: node.GET('draft.source')};
    if (kind === 'template') { value.blocks = blocks(node); value.dependencies = dependencies(node); }
    return value;
}
function equal(a, b) { return JSON.stringify(a) === JSON.stringify(b); }

export class Logic {
    initialize(node, _args) {
        this.resourceState = {saved: snapshot(node), pending: null, disposed: false, liveSequence: 0,
            nextRow: keys(node, 'draft.row_keys').length};
        const state = this.resourceState;
        const guard = event => {
            if (node.GET('res.dirty') || node.GET('res.busy')) {
                event.preventDefault(); event.returnValue = '';
            }
        };
        window.addEventListener('beforeunload', guard);
        // The same-origin administration shell owns retained iframes.
        window.parent.addEventListener('beforeunload', guard);
        // A dataController is not rendered: dispose with its rendered parent pane.
        this.page.src.renderer.onDispose(node.parentNode, () => {
            state.disposed = true;
            window.removeEventListener('beforeunload', guard);
            window.parent.removeEventListener('beforeunload', guard);
        });
        this.changed(node, {});
        void this.livePreview(node, {});
    }
    changed(node, _args) {
        const state = this.resourceState;
        if (!state || state.disposed) return;
        node.SET('res.dirty', !equal(state.saved, snapshot(node)));
    }
    async callCommand(operation, arguments_) {
        const reply = await this.page.rpc.call('data', 'command', {operation, arguments: arguments_});
        if (!reply.ok) {
            const error = new Error(reply.error.message);
            error.code = reply.error.code;
            error.definite = reply.error.code !== 'commit_uncertain';
            throw error;
        }
        return reply.result;
    }
    async save(node, _args) {
        const state = this.resourceState;
        if (!state || node.GET('res.busy')) return;
        const current = snapshot(node);
        if (!state.pending && equal(state.saved, current)) {
            node.SET('res.message', 'Nothing to save.'); return;
        }
        const kind = node.GET('res.kind');
        // A retry after an uncertain result resends the same snapshot with the same key.
        const pending = state.pending ??= {snapshot: current, operation: kind === 'media' ? 'media_save' : 'resource_save',
            arguments: {key: crypto.randomUUID(), scope: node.GET('res.scope'),
                record_id: node.GET('res.record_id'), expected_generation: node.GET('res.generation'),
                ...(kind === 'media' ? current : {kind, ...current,
                    ...(kind === 'template' ? {engine: node.GET('res.engine')}
                        : {dependencies: JSON.parse(node.GET('res.other_deps') || '[]')})})}};
        node.SET('res.busy', true);
        node.SET('res.message', 'Saving…');
        try {
            const saved = (await this.callCommand(pending.operation, pending.arguments)).records[0];
            if (state.disposed) return;
            state.saved = pending.snapshot;
            state.pending = null;
            node.SET('res.generation', saved.generation);
            node.SET('res.revision_id', saved.revision_id);
            node.SET('res.message', `Saved revision ${saved.generation}. Pages adopt it through their template.`);
        } catch (error) {
            if (state.disposed) return;
            if (error.definite) state.pending = null;
            node.SET('res.message', error.message + (state.pending
                ? ' Click Save to retry the same submitted version.' : ' Your draft is preserved.'));
        } finally {
            if (!state.disposed) { node.SET('res.busy', false); this.changed(node, {}); }
        }
    }
    apply(node, value) {
        node.SET('draft.name', value.name);
        if ('data_base64' in value) {
            node.SET('res.mime_type', value.mime_type);
            node.SET('draft.data_base64', value.data_base64);
        } else node.SET('draft.source', value.source);
        this.changed(node, {});
    }
    revert(node, _args) {
        const state = this.resourceState;
        if (!state) return;
        this.apply(node, state.saved);
        node.SET('res.message', 'Reverted to the saved revision. Blocks and dependencies keep their edits.');
    }
    async loadRevision(node, _args) {
        const revision = node.GET('res.load_revision');
        if (!revision) { node.SET('res.message', 'Choose a revision first.'); return; }
        try {
            const record = await this.page.rpc.call('data', 'read', {operation: 'record_read',
                arguments: {record_id: node.GET('res.record_id'), revision_id: revision}});
            this.apply(node, record.kind === 'media'
                ? {name: record.attributes.name, data_base64: record.sources.binary.base64,
                    mime_type: record.attributes.mime_type}
                : {name: record.attributes.name, source: record.sources.source.text});
            node.SET('res.message', `Loaded revision ${record.generation} as an unsaved draft. Save to keep it.`);
        } catch (error) {
            node.SET('res.message', error.message);
        }
    }
    addBlock(node, _args) {
        const state = this.resourceState;
        const key = 'r' + state.nextRow++;
        node.SET(`draft.block_rows.${key}.name`, 'block' + state.nextRow);
        node.SET(`draft.block_rows.${key}.format`, 'html');
        node.SET(`draft.block_rows.${key}.required`, false);
        node.SET('draft.row_keys', [...keys(node, 'draft.row_keys'), key].join(','));
    }
    removeBlock(node, {key}) {
        node.SET('draft.row_keys', keys(node, 'draft.row_keys').filter(item => item !== key).join(','));
    }
    async mediaFile(node, event) {
        const file = event.target.files?.[0];
        if (!file) return;
        const bytes = new Uint8Array(await file.arrayBuffer());
        let binary = '';
        for (const byte of bytes) binary += String.fromCharCode(byte);
        node.SET('res.mime_type', file.type || 'application/octet-stream');
        node.SET('draft.data_base64', btoa(binary));
        node.SET('res.message', `${file.name} loaded. Save to keep it.`);
        this.changed(node, {});
    }
    async livePreview(node, _args) {
        const state = this.resourceState;
        const index = node.GET('res.sample');
        if (!state || state.disposed || index === '' || index == null) return;
        const sample = JSON.parse(node.GET('res.samples'))[+index];
        // Only the latest request may update the preview; earlier replies are discarded.
        const sequence = ++state.liveSequence;
        // The unsaved source replaces the revision this sample page uses; media render as saved.
        const resources = node.GET('res.kind') === 'media' ? {}
            : {[sample.resource_revision]: node.GET('draft.source')};
        node.SET('res.live_status', 'Rendering ' + sample.label + '…');
        try {
            const result = await this.callCommand('render_draft', {variant_id: sample.variant_id,
                revision_id: sample.variant_revision, blocks: {}, resources});
            if (state.disposed || sequence !== state.liveSequence) return;
            if (result.status !== 'succeeded') {
                node.SET('res.live_status', result.diagnostics.map(d => d.message).join(' · '));
                return;
            }
            node.SET('res.preview', result.html);
            node.SET('res.live_status', sample.label + ' · draft preview, not saved, not published.');
        } catch (error) {
            if (!state.disposed && sequence === state.liveSequence) node.SET('res.live_status', error.message);
        }
    }
}
