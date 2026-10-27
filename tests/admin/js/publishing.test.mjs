import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
import {webcrypto} from 'node:crypto';
const text = await readFile(new URL('../../../src/kajenn_press/admin/pages/publishing.js', import.meta.url), 'utf8');
// One-millisecond polling keeps the build loop fast in tests.
const fast = text.replace('const POLL_INTERVAL = 1000;', 'const POLL_INTERVAL = 1;');
const {Logic} = await import('data:text/javascript;base64,' + Buffer.from(fast).toString('base64'));
globalThis.crypto ??= webcrypto;

function fixture(call, extra = {}) {
    const values = new Map(Object.entries({
        'pub.site': 's', 'pub.version': 0, 'pub.busy': false, 'pub.settings_id': 'set',
        'pub.channel_generation': 1, 'pub.channel_index': '0',
        'pub.channels': JSON.stringify([{record_id: 'set', generation: 2, channel: 'main',
            public_origin: 'https://x.test', primary_language: 'en', landing_variant: 'v1'}]),
        'pub.routes_meta': JSON.stringify({v1: {record_id: 'route', generation: 1}}),
        'pub.revisions': JSON.stringify({v1: 'v1r', v2: 'v2r'}),
        'pub.select.v1': true, 'pub.select.v2': false, ...extra
    }));
    const node = {GET: key => values.get(key), SET: (key, value) => values.set(key, value)};
    const logic = new Logic();
    logic.page = {rpc: {call}};
    return {logic, node};
}
const ok = result => ({ok: true, result});

test('build creates a candidate of the selected pages and polls until it ends', async () => {
    const calls = [];
    let polls = 0;
    const {logic, node} = fixture(async (_type, _name, args) => {
        calls.push(structuredClone(args));
        if (args.operation === 'candidate_create') return ok({record_id: 'cand'});
        if (args.operation === 'build_start') return ok({record_id: 'job'});
        polls++;
        return ok({attributes: {state: polls < 3 ? 'running' : 'succeeded', diagnostics: []}});
    });
    await logic.build(node, {});
    assert.deepEqual(calls[0].arguments.variant_revisions, ['v1r']);
    assert.equal(calls[1].arguments.candidate_id, 'cand');
    assert.equal(polls, 3);
    assert.match(node.GET('pub.message'), /Build succeeded/);
    assert.equal(node.GET('pub.busy'), false);
    assert.ok(node.GET('pub.version') >= 2);
});

test('a failed build reports its diagnostics', async () => {
    const {logic, node} = fixture(async (_type, _name, args) => {
        if (args.operation === 'candidate_create') return ok({record_id: 'cand'});
        if (args.operation === 'build_start') return ok({record_id: 'job'});
        return ok({attributes: {state: 'failed', diagnostics: [{message: 'Template error'}]}});
    });
    await logic.build(node, {});
    assert.equal(node.GET('pub.message'), 'Build failed: Template error');
});

test('activation and rollback carry the channel generation', async () => {
    const calls = [];
    const {logic, node} = fixture(async (_type, _name, args) => { calls.push(structuredClone(args)); return ok({}); });
    await logic.activate(node, {build: 'b2'});
    await logic.rollback(node, {build: 'b1'});
    assert.deepEqual(calls.map(c => [c.operation, c.arguments.build_id, c.arguments.expected_generation]),
        [['release_activate', 'b2', 1], ['release_rollback', 'b1', 1]]);
    assert.match(node.GET('pub.message'), /Rolled back/);
});

test('saving an existing channel and route sends their record and generation', async () => {
    const calls = [];
    const {logic, node} = fixture(async (_type, _name, args) => {
        calls.push(structuredClone(args));
        return ok({attributes: {path: '/en/about/'}});
    }, {'pub.routes.v1.path': 'about', 'pub.routes.v1.title': 'About', 'pub.routes.v1.description': 'd'});
    logic.fillChannel(node, {});
    assert.equal(node.GET('pub.form.public_origin'), 'https://x.test');
    await logic.saveChannel(node, {});
    await logic.saveRoute(node, {variant: 'v1'});
    assert.equal(calls[0].arguments.record_id, 'set');
    assert.equal(calls[0].arguments.expected_generation, 2);
    assert.deepEqual({...calls[1].arguments, key: undefined}, {key: undefined, variant_id: 'v1',
        path: 'about', title: 'About', description: 'd', record_id: 'route', expected_generation: 1});
    node.SET('pub.channel_index', 'new');
    logic.fillChannel(node, {});
    assert.equal(node.GET('pub.form.public_origin'), '');
});
