function declarations(node) { return JSON.parse(node.GET('page.declarations')); }
function blockSources(node) {
    const sources = {};
    for (const name of Object.keys(declarations(node))) sources[name] = node.GET('draft.blocks.' + name) ?? '';
    return sources;
}
function equal(a, b) { return JSON.stringify(a) === JSON.stringify(b); }

export class Logic {
    initialize(node, _args) {
        // saved: the block sources of the revision this editor stands on.
        this.pageState = {saved: blockSources(node), pending: null, disposed: false, liveSequence: 0};
        const state = this.pageState;
        const guard = event => {
            if (node.GET('page.dirty') || node.GET('page.busy')) {
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
        // The first preview shows the saved revision, before any edit.
        void this.livePreview(node, {});
    }
    changed(node, _args) {
        const state = this.pageState;
        if (!state || state.disposed) return;
        node.SET('page.dirty', !equal(state.saved, blockSources(node)));
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
    setBlocks(node, sources) {
        for (const [name, source] of Object.entries(sources)) node.SET('draft.blocks.' + name, source);
        this.changed(node, {});
    }
    async save(node, _args) {
        const state = this.pageState;
        if (!state || node.GET('page.busy')) return;
        const current = blockSources(node);
        if (!state.pending && equal(state.saved, current)) {
            node.SET('page.message', 'Nothing to save.'); return;
        }
        // A retry after an uncertain result resends the same snapshot with the same key.
        const formats = declarations(node);
        const pending = state.pending ??= {snapshot: current, arguments: {
            key: crypto.randomUUID(), variant_id: node.GET('page.variant_id'),
            expected_generation: node.GET('page.variant_generation'),
            template_revision: node.GET('page.template_revision'),
            blocks: Object.fromEntries(Object.entries(current).map(
                ([name, source]) => [name, {format: formats[name].format, source}]))}};
        node.SET('page.busy', true);
        node.SET('page.message', 'Saving…');
        try {
            const saved = (await this.callCommand('draft_save', pending.arguments)).records[0];
            if (state.disposed) return;
            state.saved = pending.snapshot;
            state.pending = null;
            node.SET('page.variant_generation', saved.generation);
            node.SET('page.variant_revision', saved.revision_id);
            node.SET('page.message', 'Saved a new revision. Nothing has been published.');
        } catch (error) {
            if (state.disposed) return;
            if (error.definite) state.pending = null;
            node.SET('page.message', error.message + (state.pending
                ? ' Click Save to retry the same submitted version.' : ' Your draft is preserved.'));
        } finally {
            if (!state.disposed) { node.SET('page.busy', false); this.changed(node, {}); }
        }
    }
    revert(node, _args) {
        const state = this.pageState;
        if (!state) return;
        this.setBlocks(node, state.saved);
        node.SET('page.message', 'Reverted to the saved revision.');
    }
    async loadRevision(node, _args) {
        const revision = node.GET('page.load_revision');
        if (!revision) { node.SET('page.message', 'Choose a revision first.'); return; }
        try {
            const record = await this.page.rpc.call('data', 'read', {operation: 'record_read',
                arguments: {record_id: node.GET('page.variant_id'), revision_id: revision}});
            const sources = {};
            for (const name of Object.keys(declarations(node))) {
                sources[name] = record.sources['block.' + name]?.text ?? '';
            }
            this.setBlocks(node, sources);
            node.SET('page.message', `Loaded revision ${record.generation} as an unsaved draft. Save to keep it.`);
        } catch (error) {
            node.SET('page.message', error.message);
        }
    }
    openTemplate(node, _args) {
        gramlot.publish({topic: 'open_object', parent: true},
            {kind: 'template', record_id: node.GET('page.template_id')});
    }
    async readiness(node, _args) {
        try {
            const result = await this.callCommand('readiness', {record_id: node.GET('page.variant_id'),
                revision_id: node.GET('page.variant_revision')});
            node.SET('page.message', result.ready ? 'The saved revision is ready.'
                : result.diagnostics.map(d => `${d.block}: ${d.message}`).join(' · '));
        } catch (error) {
            node.SET('page.message', error.message);
        }
    }
    async addLanguage(node, _args) {
        const state = this.pageState;
        const language = node.GET('page.new_language');
        if (!state || !language || node.GET('page.busy')) return;
        const formats = declarations(node);
        node.SET('page.busy', true);
        try {
            // The new language starts from the current blocks, recorded as a translation.
            await this.callCommand('variant_create', {key: crypto.randomUUID(),
                content_id: node.GET('page.content_id'), language,
                template_revision: node.GET('page.template_revision'),
                translated_from: node.GET('page.variant_revision'),
                blocks: Object.fromEntries(Object.entries(blockSources(node)).map(
                    ([name, source]) => [name, {format: formats[name].format, source}]))});
            if (state.disposed) return;
            node.SET('page.busy', false);
            node.SET('page.language', language);
        } catch (error) {
            if (state.disposed) return;
            node.SET('page.busy', false);
            node.SET('page.message', error.message);
        }
    }
    async useLatestTemplate(node, _args) {
        const state = this.pageState;
        if (!state || node.GET('page.busy')) return;
        // Blocks whose name and format survive move to the new revision; new blocks start empty.
        const latest = JSON.parse(node.GET('page.latest_declarations'));
        const blocks = {};
        for (const [name, source] of Object.entries(blockSources(node))) {
            if (latest[name]?.format === declarations(node)[name].format) {
                blocks[name] = {format: latest[name].format, source};
            }
        }
        node.SET('page.busy', true);
        try {
            await this.callCommand('draft_save', {key: crypto.randomUUID(), variant_id: node.GET('page.variant_id'),
                expected_generation: node.GET('page.variant_generation'),
                template_revision: node.GET('page.latest_template'), blocks});
            if (state.disposed) return;
            node.SET('page.busy', false);
            // Reload the editor: the latest template may declare other blocks.
            node.SET('page.version', node.GET('page.version') + 1);
        } catch (error) {
            if (state.disposed) return;
            node.SET('page.busy', false);
            node.SET('page.message', error.message);
        }
    }
    async livePreview(node, _args) {
        const state = this.pageState;
        if (!state || state.disposed) return;
        // Only the latest request may update the preview; earlier replies are discarded.
        const sequence = ++state.liveSequence;
        node.SET('page.live_status', 'Rendering your draft…');
        try {
            const result = await this.callCommand('render_draft', {variant_id: node.GET('page.variant_id'),
                revision_id: node.GET('page.variant_revision'), blocks: blockSources(node), resources: {}});
            if (state.disposed || sequence !== state.liveSequence) return;
            if (result.status !== 'succeeded') {
                node.SET('page.live_status', result.diagnostics.map(d => d.message).join(' · '));
                return;
            }
            node.SET('page.preview', result.html);
            node.SET('page.live_status', 'Draft preview · not saved, not published.');
        } catch (error) {
            if (!state.disposed && sequence === state.liveSequence) node.SET('page.live_status', error.message);
        }
    }
}
