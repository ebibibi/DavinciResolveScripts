"""What the bundled Resolve templates put on the `main` timeline.

The opening clip was removed because a different opening is used now; the
overlay that is only layered on top stays. See ADR-017.
"""

import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import remove_timeline_clip  # noqa: E402

TEMPLATES = {
    "paid": REPO_ROOT / "有償版用スクリプト" / "テンプレート.drp",
    "free": REPO_ROOT / "無料版用スクリプト" / "テンプレート.drp",
}


def timeline_items(template: Path) -> list[ET.Element]:
    with zipfile.ZipFile(template) as archive:
        members = remove_timeline_clip.timeline_members(archive)
        assert len(members) == 1, members
        root = ET.fromstring(archive.read(members[0]))
    # Every timeline item is the single child of an <Element> in a track's <Items>.
    return [
        element[0]
        for track in root.iter("Sm2TiTrack")
        for element in track.find("Items")
    ]


def media_pool_ids(template: Path) -> set[str]:
    # Not parsed as XML: Resolve writes tags such as <ListMgt::LmVersion>.
    with zipfile.ZipFile(template) as archive:
        folder = archive.read("MediaPool/Master/MpFolder.xml").decode("utf-8")
    return set(re.findall(r'DbId="([^"]+)"', folder))


@pytest.mark.parametrize("edition", sorted(TEMPLATES))
def test_the_opening_clip_is_gone_and_the_overlay_stays(edition):
    names = [item.findtext("Name") for item in timeline_items(TEMPLATES[edition])]

    assert not any("01_EBI_CHAN_OP" in name for name in names)
    assert names.count("MasahikoEbisuda_MicrosoftMVP.mov") == 1
    assert names.count("Big 10 - TrackTribe.mp3") == 1


@pytest.mark.parametrize("edition", sorted(TEMPLATES))
def test_the_overlay_keeps_its_place(edition):
    (overlay,) = [
        item
        for item in timeline_items(TEMPLATES[edition])
        if item.findtext("Name") == "MasahikoEbisuda_MicrosoftMVP.mov"
    ]

    assert overlay.tag == "Sm2TiVideoClip"
    assert (overlay.findtext("Start"), overlay.findtext("Duration")) == ("0", "300")


@pytest.mark.parametrize("edition", sorted(TEMPLATES))
def test_no_timeline_item_points_at_missing_media(edition):
    template = TEMPLATES[edition]
    pool = media_pool_ids(template)

    for item in timeline_items(template):
        assert item.findtext("MediaRef") in pool
        linked = item.find("LinkedItemSync")
        assert linked is None or not list(linked)


def test_removing_a_clip_leaves_an_empty_track_in_resolves_own_form():
    xml = (
        "<Sm2TiTrack>\n    <Items>\n     <Element>\n"
        '      <Sm2TiVideoClip DbId="0b5c7b9a-0001">\n       <Name>old.mov</Name>\n'
        "      </Sm2TiVideoClip>\n     </Element>\n    </Items>\n</Sm2TiTrack>\n"
    )

    updated, removed = remove_timeline_clip.without_clip(xml, "old.mov")

    assert removed == ["0b5c7b9a-0001"]
    assert updated == "<Sm2TiTrack>\n    <Items/>\n</Sm2TiTrack>\n"


def test_a_clip_still_referenced_elsewhere_is_refused():
    xml = (
        "<Items>\n     <Element>\n"
        '      <Sm2TiVideoClip DbId="0b5c7b9a-0001">\n       <Name>old.mov</Name>\n'
        "      </Sm2TiVideoClip>\n     </Element>\n"
        "     <Element>\n"
        '      <Sm2TiAudioClip DbId="b">\n       <Name>old audio</Name>\n'
        "       <LinkedItemSync>0b5c7b9a-0001</LinkedItemSync>\n"
        "      </Sm2TiAudioClip>\n     </Element>\n</Items>\n"
    )

    with pytest.raises(ValueError, match="still referenced"):
        remove_timeline_clip.without_clip(xml, "old.mov")
