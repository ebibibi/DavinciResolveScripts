"""Title delivery must preserve projects and user-customized installed files."""

import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "有償版用スクリプト"))
from build_title_presets import build_project, extract_composition, load_presets
from install_title_presets import install_presets


def test_project_addition_is_idempotent_and_preserves_other_members(tmp_path):
    source = ROOT / "有償版用スクリプト" / "テンプレート.drp"
    first = tmp_path / "first.drp"
    second = tmp_path / "second.drp"
    build_project(source, first)
    build_project(first, second)
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(first) as built:
        assert built.testzip() is None
        for name in original.namelist():
            if name != "MediaPool/Master/MpFolder.xml":
                assert built.read(name) == original.read(name)
        xml = built.read("MediaPool/Master/MpFolder.xml").decode()
        assert xml.count("<Name>テロップ</Name>") == 1
        for preset in load_presets():
            assert xml.count(f"<Name>{preset['name']}</Name>") == 1
            composition = extract_composition(xml, preset["name"])
            assert preset["text"] in composition
            assert "MediaOut1" in composition
        with zipfile.ZipFile(second) as rebuilt:
            for name in built.namelist():
                assert rebuilt.read(name) == built.read(name)


def test_install_preserves_modified_user_preset(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "one.setting").write_text("version one")
    destination = tmp_path / "installed"
    assert install_presets(source, destination) == (1, 0)
    assert install_presets(source, destination) == (0, 0)
    (destination / "one.setting").write_text("user customization")
    (source / "one.setting").write_text("version two")
    assert install_presets(source, destination) == (0, 1)
    assert (destination / "one.setting").read_text() == "user customization"


def test_install_upgrades_unmodified_owned_files(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "one.setting").write_text("version one")
    destination = tmp_path / "installed"
    install_presets(source, destination)
    (source / "one.setting").write_text("version two")
    assert install_presets(source, destination) == (1, 0)
    assert (destination / "one.setting").read_text() == "version two"


def test_unowned_existing_file_is_not_overwritten(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "one.setting").write_text("ours")
    destination = tmp_path / "installed"
    destination.mkdir()
    (destination / "one.setting").write_text("someone else")
    assert install_presets(source, destination) == (0, 1)
    assert (destination / "one.setting").read_text() == "someone else"


def lua_graph(text):
    from lupa import LuaRuntime

    lua = LuaRuntime()
    lua.execute("""
        function ordered() return function(t) return t end end
        for _, name in ipairs({"Input", "InstanceInput", "InstanceOutput", "TextPlus",
                               "MacroOperator", "RectangleMask", "Background", "Merge",
                               "Transform", "MediaOut"}) do
            _G[name] = function(t) t._kind = name; return t end
        end
    """)
    return lua.eval(text)


def test_all_fusion_graphs_parse_and_have_connected_outputs():
    """Evaluate Lua syntax and graph links, not a substitute for Fusion rendering."""
    from title_graph import composition_tools, setting_text

    for preset in load_presets():
        setting = lua_graph(setting_text(preset))
        macro = setting["Tools"]["Template"]
        nodes = macro["Tools"]
        for key, control in macro["Inputs"].items():
            assert (
                nodes[control["SourceOp"]]["Inputs"][control["Source"]] is not None
            ), key
        for name, node in nodes.items():
            for control in node["Inputs"].values():
                if control["SourceOp"]:
                    assert nodes[control["SourceOp"]] is not None, name
                    assert control["Source"] in ("Output", "Mask")
        comp = lua_graph(composition_tools(preset).rstrip("\0"))
        assert comp["MediaOut1"]["Inputs"]["Input"]["SourceOp"] == "Template"
        output = comp["MediaOut1"]["Inputs"]["Input"]["Source"]
        assert output == "Output"
        assert comp["Template"]["Outputs"]["MainOutput1"] is not None
        # Reading two assets must produce independent node objects.
        other = lua_graph(setting_text(preset))
        nodes["MainText"]["Inputs"]["StyledText"]["Value"] = "changed"
        assert (
            other["Tools"]["Template"]["Tools"]["MainText"]["Inputs"]["StyledText"][
                "Value"
            ]
            == preset["text"]
        )


def test_composition_containers_reject_wrong_sizes():
    from title_archive import pack_composition, unpack_composition

    packed = pack_composition("{ abc = 1 }\0")
    assert unpack_composition(packed) == "{ abc = 1 }"
    with pytest.raises(ValueError):
        unpack_composition("ffffffff" + packed[8:])


def test_original_names_and_transforms_are_independent():
    import re

    import zstandard
    from title_archive import fields, generator_blocks

    source = ROOT / "有償版用スクリプト" / "テンプレート.drp"
    with zipfile.ZipFile(source) as archive:
        xml = archive.read("MediaPool/Master/MpFolder.xml").decode()
    ids = []
    for block in generator_blocks(xml):
        name = re.search(r"<Name>(.*?)</Name>", block)[1]
        ids.extend(re.findall(r'DbId="([a-f0-9-]+)"', block))
        blob = bytes.fromhex(re.search(r"<FieldsBlob>(.*?)</FieldsBlob>", block)[1])
        outer = fields(zstandard.ZstdDecompressor().decompress(blob[9:]))
        inner = fields(next(value for number, _, value in outer if number == 1))
        assert next(value for number, _, value in inner if number == 2).decode() == name
        if name.startswith("EBI_"):
            assert all(number != 3 for number, _, _ in inner)
        else:
            assert any(number == 3 for number, _, _ in inner)
    assert len(ids) == len(set(ids))


def test_installer_cli_and_repeat_install(tmp_path):
    import subprocess

    command = [
        sys.executable,
        str(ROOT / "有償版用スクリプト/install_title_presets.py"),
        "--destination",
        str(tmp_path / "Titles/EBI"),
    ]
    first = subprocess.run(command, capture_output=True, text=True, check=True)
    second = subprocess.run(command, capture_output=True, text=True, check=True)
    assert "12 installed/updated" in first.stdout
    assert "0 installed/updated" in second.stdout
    assert len(list((tmp_path / "Titles/EBI").glob("*.setting"))) == 12
