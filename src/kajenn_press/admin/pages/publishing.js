const POLL_INTERVAL = 1000;  // ms between build_status calls
const POLL_LIMIT = 300;  // polls before giving up on a build
const PREVIEW_LIFETIME = 3600;  // seconds a preview link stays valid
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
function json(node, path) { return JSON.parse(node.GET(path) || 'null'); }

export class Logic {
    async callCommand(operation, arguments_) {
        const reply = await this.page.rpc.call('data', 'command', {operation, arguments: arguments_});
        if (!reply.ok) throw new Error(reply.error.message);
        return reply.result;
    }
    refresh(node) { node.SET('pub.version', (node.GET('pub.version') ?? 0) + 1); }
    async run(node, label, work) {
        if (node.GET('pub.busy')) return;
        node.SET('pub.busy', true);
        node.SET('pub.message', label + '…');
        try {
            node.SET('pub.message', await work());
        } catch (error) {
            node.SET('pub.message', error.message);
        } finally {
            node.SET('pub.busy', false);
        }
    }
    fillChannel(node, _args) {
        const index = node.GET('pub.channel_index');
        const channel = index === 'new' ? null : json(node, 'pub.channels')[+index];
        node.SET('pub.form.channel', channel?.channel ?? 'main');
        node.SET('pub.form.public_origin', channel?.public_origin ?? '');
        node.SET('pub.form.primary_language', channel?.primary_language ?? node.GET('pub.form.primary_language'));
        node.SET('pub.form.landing_variant', channel?.landing_variant ?? node.GET('pub.form.landing_variant'));
    }
    saveChannel(node, _args) {
        const index = node.GET('pub.channel_index');
        const channel = index === 'new' ? null : json(node, 'pub.channels')[+index];
        return this.run(node, 'Saving the channel', async () => {
            await this.callCommand('publication_settings_save', {key: crypto.randomUUID(),
                site_id: node.GET('pub.site'), channel: node.GET('pub.form.channel'),
                public_origin: node.GET('pub.form.public_origin'),
                primary_language: node.GET('pub.form.primary_language'),
                landing_variant: node.GET('pub.form.landing_variant'),
                ...(channel ? {record_id: channel.record_id, expected_generation: channel.generation} : {})});
            this.refresh(node);
            return 'Channel saved.';
        });
    }
    saveRoute(node, {variant}) {
        const route = json(node, 'pub.routes_meta')[variant];
        const field = name => node.GET(`pub.routes.${variant}.${name}`);
        return this.run(node, 'Saving the route', async () => {
            const saved = await this.callCommand('publication_route_save', {key: crypto.randomUUID(),
                variant_id: variant, path: field('path'), title: field('title'), description: field('description'),
                ...(route ? {record_id: route.record_id, expected_generation: route.generation} : {})});
            this.refresh(node);
            return 'Route saved: ' + saved.attributes.path;
        });
    }
    build(node, _args) {
        const settings_id = node.GET('pub.settings_id');
        const revisions = json(node, 'pub.revisions');
        const selected = Object.keys(revisions).filter(vid => node.GET('pub.select.' + vid));
        return this.run(node, 'Building', async () => {
            if (!selected.length) throw new Error('Select at least one page with a route.');
            // The candidate fixes the latest saved revision of each selected page.
            const candidate = await this.callCommand('candidate_create', {key: crypto.randomUUID(),
                settings_id, variant_revisions: selected.map(vid => revisions[vid])});
            const job = await this.callCommand('build_start', {key: crypto.randomUUID(), candidate_id: candidate.record_id});
            this.refresh(node);
            for (let poll = 0; poll < POLL_LIMIT; poll++) {
                const status = await this.callCommand('build_status', {build_id: job.record_id});
                const {state, diagnostics} = status.attributes;
                if (state !== 'queued' && state !== 'running') {
                    this.refresh(node);
                    if (state === 'succeeded') return 'Build succeeded. Preview it or activate it.';
                    return `Build ${state}: ` + diagnostics.map(d => d.message).join(' · ');
                }
                node.SET('pub.message', `Building… ${state}`);
                await sleep(POLL_INTERVAL);
            }
            return 'The build is still running. Its state appears in the list.';
        });
    }
    previewLink(node, {build}) {
        return this.run(node, 'Creating a preview link', async () => {
            const grant = await this.callCommand('preview_grant_create', {key: crypto.randomUUID(),
                build_id: build, lifetime_seconds: PREVIEW_LIFETIME});
            node.SET('pub.preview_url', grant.url);
            return 'Private preview link, valid for one hour:';
        });
    }
    release(node, operation, build, done) {
        return this.run(node, operation === 'release_activate' ? 'Activating' : 'Rolling back', async () => {
            await this.callCommand(operation, {key: crypto.randomUUID(), settings_id: node.GET('pub.settings_id'),
                build_id: build, expected_generation: node.GET('pub.channel_generation')});
            this.refresh(node);
            return done;
        });
    }
    activate(node, {build}) {
        return this.release(node, 'release_activate', build, 'Release activated: the channel now serves this build.');
    }
    rollback(node, {build}) {
        return this.release(node, 'release_rollback', build, 'Rolled back: the channel serves this earlier build again.');
    }
}
