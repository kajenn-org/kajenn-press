function templateSnapshot(node) { // wf:phase-1:new
    return {name: node.GET('draft.template_name'), source: node.GET('draft.source')};
}
function pageSnapshot(node) { // wf:phase-1:new
    return {title: node.GET('draft.title'), language: node.GET('draft.language'),
        body: node.GET('draft.body'), template_revision: node.GET('draft.template_revision')};
}
function equal(a, b) { return JSON.stringify(a) === JSON.stringify(b); } // wf:phase-1:new

export class Logic {
    initialize(node, _args) { // wf:phase-1:new
        this.authorState = {template: node.GET('draft.template_id') ? templateSnapshot(node) : null,
            page: node.GET('draft.variant_id') ? pageSnapshot(node) : null, pending: {}, disposed: false};
        const state = this.authorState;
        const guard = event => { // wf:phase-1:new
            if (node.GET('author.dirty') || node.GET('author.busy')) {
                event.preventDefault(); event.returnValue = '';
            }
        };
        window.addEventListener('beforeunload', guard);
        // The same-origin administration shell owns retained iframes.
        window.parent.addEventListener('beforeunload', guard);
        this.page.src.renderer.onDispose(node, () => { // wf:phase-1:new
            state.disposed = true;
            window.removeEventListener('beforeunload', guard);
            window.parent.removeEventListener('beforeunload', guard);
        });
        this.changed(node, {});
    }
    changed(node, _args) { // wf:phase-1:new
        const state = this.authorState;
        if (!state || state.disposed) return;
        node.SET('author.dirty', !equal(state.template, templateSnapshot(node)) ||
            !equal(state.page, pageSnapshot(node)));
    }
    async callCommand(operation, arguments_) { // wf:phase-1:new
        const reply = await this.page.rpc.call('data', 'command', {operation, arguments: arguments_});
        if (!reply.ok) {
            const error = new Error(reply.error.message);
            error.code = reply.error.code;
            error.definite = reply.error.code !== 'commit_uncertain';
            throw error;
        }
        return reply.result;
    }
    async saveTemplate(node, _args) { // wf:phase-1:new
        const state = this.authorState;
        if (!state || node.GET('author.busy')) return;
        const current = templateSnapshot(node);
        if (!state.pending.template && equal(state.template, current)) {
            node.SET('author.message', 'Template is already saved.'); return;
        }
        const pending = state.pending.template ??= {snapshot: current, arguments: {
            key: crypto.randomUUID(), scope: node.GET('draft.template_scope'), kind: 'template',
            name: current.name, source: current.source, engine: 'gramlot',
            blocks: {body: {format: 'html', required: true}},
            dependencies: node.GET('draft.dependencies'),
            record_id: node.GET('draft.template_id') || null,
            expected_generation: node.GET('draft.template_generation')
        }};
        node.SET('author.busy', true);
        try {
            const result = await this.callCommand('resource_save', pending.arguments);
            if (state.disposed) return;
            const saved = result.records[0];
            state.template = pending.snapshot;
            delete state.pending.template;
            node.SET('draft.template_id', saved.record_id);
            node.SET('draft.template_generation', saved.generation);
            node.SET('draft.template_revision', saved.revision_id);
            node.SET('author.refresh', node.GET('author.refresh') + 1);
            node.SET('author.message', 'Template saved. Write your content, then save the page.');
            node.SET('author.tab', 'content');
        } catch (error) {
            if (state.disposed) return;
            // Known rejection has no uncertain effect. Transport/commit uncertainty keeps the snapshot.
            if (error.definite) delete state.pending.template;
            node.SET('author.message', error.message + (state.pending.template ? ' Click Save template to retry the same submitted version.' : ' Your draft is preserved.'));
        } finally {
            if (!state.disposed) { node.SET('author.busy', false); this.changed(node, {}); }
        }
    }
    async savePage(node, _args) { // wf:phase-1:new
        const state = this.authorState;
        if (!state || node.GET('author.busy')) return;
        if (!state.pending.page && (!node.GET('draft.template_revision') || !equal(state.template, templateSnapshot(node)))) {
            node.SET('author.message', 'Save your template first.'); return;
        }
        const current = pageSnapshot(node);
        if (!state.pending.page && equal(state.page, current)) {
            node.SET('author.message', 'Page is already saved.'); return;
        }
        const pending = state.pending.page ??= {snapshot: current,
            content: {site_id: node.GET('draft.site'), title: current.title, key: crypto.randomUUID()},
            content_id: node.GET('draft.content_id'), variant_id: node.GET('draft.variant_id'),
            generation: node.GET('draft.variant_generation'), key: crypto.randomUUID()};
        node.SET('author.busy', true);
        try {
            if (!pending.content_id) {
                const created = await this.callCommand('content_create', pending.content);
                pending.content_id = created.records[0].record_id;
                if (state.disposed) return;
                node.SET('draft.content_id', pending.content_id);
            }
            const arguments_ = {key: pending.key, template_revision: pending.snapshot.template_revision,
                blocks: {body: {format: 'html', source: pending.snapshot.body}}};
            if (pending.variant_id) Object.assign(arguments_, {variant_id: pending.variant_id,
                expected_generation: pending.generation});
            else Object.assign(arguments_, {content_id: pending.content_id, language: pending.snapshot.language});
            const result = await this.callCommand(pending.variant_id ? 'draft_save' : 'variant_create', arguments_);
            if (state.disposed) return;
            const saved = result.records[0];
            state.page = pending.snapshot;
            delete state.pending.page;
            node.SET('draft.variant_id', saved.record_id);
            node.SET('draft.variant_generation', saved.generation);
            node.SET('draft.variant_revision', saved.revision_id);
            node.SET('author.refresh', node.GET('author.refresh') + 1);
            node.SET('author.message', 'Page saved. Click Render saved page to see the result.');
        } catch (error) {
            if (state.disposed) return;
            if (error.definite) delete state.pending.page;
            node.SET('author.message', error.message + (state.pending.page ? ' Click Save page to retry the same submitted version.' : ' Your draft is preserved.'));
        } finally {
            if (!state.disposed) { node.SET('author.busy', false); this.changed(node, {}); }
        }
    }
    async preview(node, _args) { // wf:phase-1:new
        const state = this.authorState;
        if (!state || node.GET('author.busy')) return;
        if (node.GET('author.dirty') || !node.GET('draft.variant_id')) {
            node.SET('author.message', 'Save the template and page before rendering.'); return;
        }
        node.SET('author.busy', true);
        node.SET('author.message', 'Rendering the saved page…');
        try {
            const result = await this.callCommand('render_preview', {variant_id: node.GET('draft.variant_id'),
                revision_id: node.GET('draft.variant_revision')});
            if (state.disposed) return;
            if (result.status !== 'succeeded') throw new Error(result.diagnostics.map(d => d.message).join(' · '));
            node.SET('author.preview', result.html);
            node.SET('author.tab', 'preview');
            node.SET('author.message', 'Rendered saved revisions. Nothing has been published.' +
                (result.diagnostics.length ? ' ' + result.diagnostics.map(d => d.message).join(' · ') : ''));
        } catch (error) {
            if (!state.disposed) node.SET('author.message', error.message);
        } finally {
            if (!state.disposed) node.SET('author.busy', false);
        }
    }
}
