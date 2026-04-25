import os
import tempfile

from PIL import Image

from gif_transformer import GIFTransformer


def test_already_compliant_unchanged():
    t = GIFTransformer(0.66, 2.5)
    assert t.target_size(800, 600) == (800, 600)
    assert t.target_size(1000, 1000) == (1000, 1000)
    # exact limits count as compliant
    assert t.target_size(2500, 1000) == (2500, 1000)
    assert t.target_size(66, 100) == (66, 100)


def test_too_wide_gets_taller():
    t = GIFTransformer(0.66, 2.5)
    w, h = t.target_size(3000, 500)
    assert t.compliant(w, h)
    # the short side must not explode past the cap
    assert h <= 500 * 1.5


def test_too_tall_gets_wider():
    t = GIFTransformer(0.66, 2.5)
    w, h = t.target_size(500, 3000)
    assert t.compliant(w, h)
    assert w <= 500 * 1.5 + 1  # +1 for the pixel nudge into the limits


def test_zero_height_not_compliant():
    assert not GIFTransformer(0.66, 2.5).compliant(100, 0)


def make_gif(path, size):
    Image.new("P", size).save(path, format="GIF")


def test_transform_skips_compliant_gif(tmp_path):
    path = str(tmp_path / "ok.gif")
    make_gif(path, (100, 100))
    assert GIFTransformer(0.66, 2.5).transform(path) == path


def test_transform_pads_tall_gif(tmp_path):
    path = str(tmp_path / "tall.gif")
    make_gif(path, (100, 300))
    t = GIFTransformer(0.66, 2.5)

    info = t.info(path)
    assert info["compliant"] is False
    assert info["height"] == 300

    out = t.transform(path)
    assert out != path
    try:
        with Image.open(out) as img:
            assert img.format == "GIF"
            assert t.compliant(*img.size)
    finally:
        t.cleanup(out)
    assert not os.path.exists(out)


def test_cleanup_removes_files_inside_temp_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    path = tmp_path / "x.gif"
    make_gif(str(path), (10, 10))
    GIFTransformer(0.66, 2.5).cleanup(str(path))
    assert not path.exists()


def test_cleanup_refuses_paths_outside_temp_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "base"))
    keep = tmp_path / "elsewhere" / "keep.gif"
    keep.parent.mkdir()
    make_gif(str(keep), (10, 10))
    GIFTransformer(0.66, 2.5).cleanup(str(keep))
    assert keep.exists()
