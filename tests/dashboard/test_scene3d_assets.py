"""Regression guards for custom Streamlit 3D component bootstrapping."""
from pathlib import Path
import pytest

COMPONENT = Path(__file__).resolve().parents[2] / "dashboard/components/solar3d_drag"


def test_iframe_sends_ready_before_importing_renderer():
    html = (COMPONENT / "index.html").read_text(encoding="utf-8")
    # Streamlit must receive the handshake even when WebGL/Three.js fails.
    assert "streamlit:componentReady" in html
    assert "streamlit:render" in html
    assert "editor.bundle.js" in html
    assert html.index("streamlit:componentReady") < html.index('src="./editor.bundle.js"')


def test_frontend_does_not_request_three_from_external_cdn():
    html = (COMPONENT / "index.html").read_text(encoding="utf-8")
    assert "cdn.jsdelivr.net" not in html
    assert "type=\"importmap\"" not in html
    assert "editor.bundle.js" in html
    pkg = (COMPONENT / "package.json").read_text(encoding="utf-8")
    assert '"three": "0.169.0"' in pkg
    assert '"esbuild": "0.24.0"' in pkg


def test_compiled_bundle_is_self_hosted_when_present():
    bundle = COMPONENT / "editor.bundle.js"
    if not bundle.is_file():
        pytest.skip("Bundle é gerado por npm no CI e no Docker")
    assert bundle.stat().st_size > 100000
    source = bundle.read_text(encoding="utf-8")
    assert "streamlit:render" in source
    assert "cdn.jsdelivr.net" not in source
