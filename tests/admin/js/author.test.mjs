import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
import {webcrypto} from 'node:crypto';
const text = await readFile(new URL('../../../src/kajenn_press/admin/pages/author.js', import.meta.url), 'utf8');
const {Logic} = await import('data:text/javascript;base64,' + Buffer.from(text).toString('base64'));
globalThis.crypto ??= webcrypto;
globalThis.window = {addEventListener() {}, removeEventListener() {}};
window.parent = window;
function fixture(call) {
    const values = new Map(Object.entries({
        'draft.site': 'site', 'draft.template_scope': 'site:site',
        'draft.template_name': 'Template', 'draft.source': 'original template',
        'draft.template_id': '', 'draft.template_revision': '', 'draft.template_generation': 0,
        'draft.dependencies': [], 'draft.content_id': '', 'draft.variant_id': '',
        'draft.variant_generation': 0, 'draft.title': 'Page', 'draft.language': 'en',
        'draft.body': '<p>Original</p>', 'author.refresh': 0, 'author.busy': false
    }));
    // Like the Gramlot renderer, only the rendered pane accepts dispose callbacks.
    const pane = {};
    const node = {GET: key => values.get(key), SET: (key, value) => values.set(key, value), parentNode: pane};
    const logic = new Logic();
    let dispose;
    const onDispose = (target, fn) => {
        if (target !== pane) throw new Error('Source node is not mounted');
        dispose = fn;
    };
    logic.page = {rpc: {call}, src: {renderer: {onDispose}}};
    logic.initialize(node, {});
    return {logic, node, dispose: () => dispose()};
}
function saved(record) { return {ok: true, result: {records: [record]}}; }

test('uncertain template retries its snapshot/key and preserves later typing', async () => {
    const calls = [];
    const {logic, node} = fixture(async (_type, _name, args) => {
        calls.push(structuredClone(args));
        if (calls.length === 1) { const error = new Error('connection lost'); error.code = 'network_error'; throw error; }
        return saved({record_id: 'template', revision_id: 'revision', generation: 1});
    });
    await logic.saveTemplate(node, {});
    node.SET('draft.source', 'typed after uncertainty');
    await logic.saveTemplate(node, {});
    assert.deepEqual(calls[0], calls[1]);
    assert.equal(node.GET('draft.source'), 'typed after uncertainty');
    assert.equal(node.GET('author.dirty'), true);
    assert.equal(logic.authorState.template.source, 'original template');
});

test('partial page creation retries variant without another content record', async () => {
    const calls = [];
    let failed = false;
    const {logic, node} = fixture(async (_type, _name, args) => {
        calls.push(structuredClone(args));
        if (args.operation === 'resource_save') return saved({record_id: 't', revision_id: 'tr', generation: 1});
        if (args.operation === 'content_create') return saved({record_id: 'c'});
        if (!failed) { failed = true; throw new Error('connection lost'); }
        return saved({record_id: 'v', revision_id: 'vr', generation: 1});
    });
    await logic.saveTemplate(node, {});
    await logic.savePage(node, {});
    node.SET('draft.body', '<p>Later typing</p>');
    await logic.savePage(node, {});
    assert.equal(calls.filter(c => c.operation === 'content_create').length, 1);
    const variants = calls.filter(c => c.operation === 'variant_create');
    assert.deepEqual(variants[0], variants[1]);
    assert.equal(node.GET('draft.body'), '<p>Later typing</p>');
    assert.equal(node.GET('author.dirty'), true);
});

test('typing during save remains dirty; disposed editors reject late results', async () => {
    let resolve;
    const {logic, node, dispose} = fixture(() => new Promise(r => { resolve = r; }));
    const pending = logic.saveTemplate(node, {});
    node.SET('draft.source', 'later');
    resolve(saved({record_id: 't', revision_id: 'tr', generation: 1}));
    await pending;
    assert.equal(node.GET('draft.source'), 'later');
    assert.equal(node.GET('author.dirty'), true);
    const last = logic.saveTemplate(node, {});
    dispose();
    resolve(saved({record_id: 't', revision_id: 'tr2', generation: 2}));
    await last;
    assert.equal(node.GET('draft.template_revision'), 'tr');
});

test('a new untouched draft is clean until the first edit', () => {
    const {logic, node} = fixture(async () => { throw new Error('no call expected'); });
    assert.equal(node.GET('author.dirty'), false);
    node.SET('draft.body', '<p>Edited</p>');
    logic.changed(node, {});
    assert.equal(node.GET('author.dirty'), true);
    node.SET('draft.body', '<p>Original</p>');
    logic.changed(node, {});
    assert.equal(node.GET('author.dirty'), false);
});

test('live preview keeps only the latest reply and drafts the template only when writable', async () => {
    const calls = [], replies = [];
    const {logic, node} = fixture((_type, _name, args) => {
        calls.push(structuredClone(args));
        return new Promise(resolve => replies.push(resolve));
    });
    await logic.livePreview(node, {});
    assert.equal(calls.length, 0, 'an unsaved page has no variant to render');
    node.SET('draft.variant_id', 'v');
    node.SET('draft.variant_revision', 'vr');
    node.SET('author.writable', true);
    logic.authorState.page = {title: 'Page', language: 'en', body: '<p>Original</p>', template_revision: 'tr'};
    logic.authorState.template = {name: 'Template', source: 'original template'};
    node.SET('draft.template_revision', 'tr');
    node.SET('draft.body', '<p>First</p>');
    const first = logic.livePreview(node, {});
    node.SET('draft.source', 'edited template');
    node.SET('draft.body', '<p>Second</p>');
    const second = logic.livePreview(node, {});
    assert.deepEqual(calls[0].arguments.resources, {});
    assert.deepEqual(calls[1].arguments.resources, {tr: 'edited template'});
    assert.deepEqual(calls[1].arguments.blocks, {body: '<p>Second</p>'});
    replies[1]({ok: true, result: {status: 'succeeded', html: 'second', diagnostics: []}});
    await second;
    replies[0]({ok: true, result: {status: 'succeeded', html: 'first', diagnostics: []}});
    await first;
    assert.equal(node.GET('author.preview'), 'second');
    node.SET('author.writable', false);
    const third = logic.livePreview(node, {});
    assert.deepEqual(calls[2].arguments.resources, {});
    replies[2]({ok: true, result: {status: 'failed', html: '', diagnostics: [{message: 'Broken template'}]}});
    await third;
    assert.equal(node.GET('author.preview'), 'second');
    assert.equal(node.GET('author.live_status'), 'Broken template');
});
