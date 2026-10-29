import {IndexLogic} from '@gramlot/gramlot/page';

// The index's Logic with the icon column's two actions (index.py, d-gramlot-shell).
// A page Logic cannot extend another class: the index mount is delegated.
export class Logic {
    indexMount(node) { return IndexLogic.prototype.indexMount.call(this, node); }
    pressToggleNavigation() {
        const builder = this.page.src.builder, open = builder.data.getItem('index.navigationOpen');
        builder.nodeById('pressNavigation').setAttr({drawer: open ? 'close' : true});
    }
    async pressSignOut() {
        await this.page.rpc.call('data', 'sign_out', {});
        window.location.reload();
    }
}
