import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
import {webcrypto} from 'node:crypto';
const text = await readFile(new URL('../../../src/kajenn_press/admin/pages/resource.js', import.meta.url), 'utf8');
const {Logic} = await import('data:text/javascript;base64,' + Buffer.from(text).toString('base64'));
globalThis.crypto ??= webcrypto;
globalThis.window = {addEventListener() {}, removeEventListener() {}};
window.parent = window;

const SAMPLES = JSON.stringify([{label: 'Home · en', variant_id: 'v', variant_revision: 'vr', resource_revision: 'old'}]);

function fixture(kind, extra, call) {
    const values = new Map(Object.entries({
        'res.kind': kind, 'res.scope': 'site:s', 'res.record_id': 'r', 'res.generation': 3,
        'res.engine': 'gramlot', 'res.samples': SAMPLES, 'res.sample': '0', 'res.busy': false,
        'res.other_deps': '[]', 'draft.name': 'Styles', 'draft.source': 'main{}', ...extra
    }));
    const pane = {};
    const node = {GET: key => values.get(key), SET: (key, value) => values.set(key, value), parentNode: pane};
    const logic = new Logic();
    logic.page = {rpc: {call}, src: {renderer: {onDispose: (target, _fn) => {
        if (target !== pane) throw new Error('Source node is not mounted');
    }}}};
    return {logic, node};
}
const rendered = html => ({ok: true, result: {status: 'succeeded', html, diagnostics: []}});
const saved = {ok: true, result: {records: [{record_id: 'r', revision_id: 'new', generation: 4}]}};

test('a stylesheet saves its source and keeps its own dependencies', async () => {
    const calls = [];
    const {logic, node} = fixture('css', {'res.other_deps': '["media-rev"]'}, async (_type, _name, args) => {
        calls.push(structuredClone(args));
        return args.operation === 'render_draft' ? rendered('page') : saved;
    });
    logic.initialize(node, {});
    node.SET('draft.source', 'main{color:red}');
    logic.changed(node, {});
    assert.equal(node.GET('res.dirty'), true);
    await logic.save(node, {});
    const save = calls.find(c => c.operation === 'resource_save').arguments;
    assert.deepEqual({...save, key: undefined}, {key: undefined, scope: 'site:s', record_id: 'r',
        expected_generation: 3, kind: 'css', name: 'Styles', source: 'main{color:red}',
        dependencies: ['media-rev']});
    assert.equal(node.GET('res.generation'), 4);
    assert.equal(node.GET('res.dirty'), false);
});

test('a template saves its block rows and chosen dependency revisions', async () => {
    const calls = [];
    const {logic, node} = fixture('template', {
        'draft.row_keys': 'r0', 'draft.block_rows.r0.name': 'body', 'draft.block_rows.r0.format': 'html',
        'draft.block_rows.r0.required': true, 'draft.dep_keys': 'd_a,d_b',
        'draft.deps.d_a.on': true, 'draft.deps.d_a.revision': 'a2',
        'draft.deps.d_b.on': false, 'draft.deps.d_b.revision': 'b1', 'res.other_deps': '["tpl-dep"]'
    }, async (_type, _name, args) => {
        calls.push(structuredClone(args));
        return args.operation === 'render_draft' ? rendered('page') : saved;
    });
    logic.initialize(node, {});
    logic.addBlock(node, {});
    node.SET('draft.block_rows.r1.name', 'aside');
    node.SET('draft.block_rows.r1.format', 'markdown');
    logic.changed(node, {});
    assert.equal(node.GET('res.dirty'), true);
    await logic.save(node, {});
    const save = calls.find(c => c.operation === 'resource_save').arguments;
    assert.equal(save.engine, 'gramlot');
    assert.deepEqual(save.blocks, {body: {format: 'html', required: true},
        aside: {format: 'markdown', required: false}});
    assert.deepEqual(save.dependencies, ['tpl-dep', 'a2']);
    logic.removeBlock(node, {key: 'r1'});
    assert.equal(node.GET('draft.row_keys'), 'r0');
});

test('the preview replaces the revision the sample page uses and keeps the latest reply', async () => {
    const calls = [], replies = [];
    const {logic, node} = fixture('css', {}, (_type, _name, args) => {
        calls.push(structuredClone(args));
        return new Promise(resolve => replies.push(resolve));
    });
    logic.initialize(node, {});
    node.SET('draft.source', 'main{color:blue}');
    const latest = logic.livePreview(node, {});
    assert.deepEqual(calls[1].arguments, {variant_id: 'v', revision_id: 'vr', blocks: {},
        resources: {old: 'main{color:blue}'}});
    replies[1](rendered('latest'));
    await latest;
    replies[0](rendered('first'));
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(node.GET('res.preview'), 'latest');
});

test('a media file is read as base64 and saved with its type', async () => {
    const calls = [];
    const {logic, node} = fixture('media', {'draft.data_base64': 'AAA=', 'res.mime_type': 'image/png'},
        async (_type, _name, args) => {
            calls.push(structuredClone(args));
            return args.operation === 'render_draft' ? rendered('page') : saved;
        });
    logic.initialize(node, {});
    assert.deepEqual(calls[0].arguments.resources, {}, 'media render as saved');
    const file = {name: 'logo.gif', type: 'image/gif', arrayBuffer: async () => new Uint8Array([71, 73, 70]).buffer};
    await logic.mediaFile(node, {target: {files: [file]}});
    assert.equal(node.GET('draft.data_base64'), 'R0lG');
    await logic.save(node, {});
    const save = calls.find(c => c.operation === 'media_save').arguments;
    assert.equal(save.mime_type, 'image/gif');
    assert.equal(save.data_base64, 'R0lG');
    assert.equal(save.kind, undefined);
});
