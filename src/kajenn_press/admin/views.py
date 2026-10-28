"""Administration page base: sign-in and sign-out through Gramlot Source."""

import asyncio
from uuid import uuid4

from gramlot import Page as GramlotPage
from gramlot import endpoint

from kajenn_press.admin.host import CURRENT_REQUEST, LOGO_SRC


def literal_text(pane, tag, text, **attributes):
    """Text from Data as literal text: an element whose value starts with ^ or = stays text."""
    path = "display_text." + uuid4().hex
    pane.dataSetter(path, text)
    return getattr(pane, tag)("^" + path, **attributes)


class AdminPage(GramlotPage):
    def login_view(self, root):
        root.dataSetter("login.username", "")
        root.dataSetter("login.password", "")
        root.dataSetter("login.error", "")
        box = root.main(class_="login-shell").section(class_="login-card")
        box.img(src=LOGO_SRC, width="160", height="160", alt="Kajenn Press", class_="login-logo")
        box.h1("Sign in to your sites")
        box.textbox(
            value="^login.username",
            lbl="Username",
            lbl_position="TL",
            live=True,
            width="100%",
            box_margin_bottom="16px",
        )
        box.passwordbox(
            value="^login.password",
            lbl="Password",
            lbl_position="TL",
            live=True,
            width="100%",
            box_margin_bottom="16px",
        )
        box.button("Sign in").dataRpc(
            "sign_in",
            username="=login.username",
            password="=login.password",
            _onResult="this.SET('login.password',''); if(!result){window.location.reload();}else{this.SET('login.error',result)}",
            _onError="this.SET('login.password','');this.SET('login.error','Sign-in unavailable')",
        )
        box.p("^login.error", role="status")

    @endpoint
    async def sign_in(self, username="", password=""):
        request = CURRENT_REQUEST.get()
        server_app = request.server.application_at("_server")
        result = await asyncio.to_thread(
            server_app.login, identity=username, password=password, _request=request
        )
        return "Sign-in failed" if "error" in result else ""

    @endpoint(auth="editor")
    def sign_out(self):
        request = CURRENT_REQUEST.get()
        request.server.session_store.delete(request.session.id)
        return True
