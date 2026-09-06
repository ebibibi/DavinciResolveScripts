# Edit page Inspector is empty for a Media Pool title

## Symptom

A bundled title placed from the Media Pool renders correctly, but selecting it
and opening **Inspector > Video > Title** shows only the title name and its
enable toggle. No text box, no font, no color. The text can then only be
changed on the Fusion page, which defeats the point of the library.

## Cause

The Edit page builds that control panel from `CustomData.TEMPLATE_ID` in the
composition header, not from the Fusion graph. A generator whose header lacks
the marker gets no panel at all.

`tools/title_archive.py` rebuilds the header from scratch when it repacks a
composition, and the first version of that header omitted `CustomData`.

## What is *not* the cause

Ruled out by building each variant and reading the Inspector in Resolve 20.1:

| Variant | Inspector |
|---|---|
| `Template` is a `MacroOperator`, no `TEMPLATE_ID` | empty |
| `Template` is a plain `TextPlus`, no `TEMPLATE_ID` | empty |
| `MacroOperator` keeping the native metadata field 3 | empty |
| `MacroOperator` with `TEMPLATE_ID` | **full panel** |
| Same title inserted from the Effects Library | full panel |

So it is neither the macro wrapper, nor the tool type named `Template`, nor the
stripped protobuf field. Effects Library titles are unaffected because Resolve
builds their panel from the installed `.setting` macro instead.

## Fix

`pack_composition()` writes `CustomData = { TEMPLATE_ID = "<title name>" }`.
Resolve only checks that the marker exists, so the panel does not depend on the
matching `.setting` being installed in the Effects Library. A bogus id renders
the same full panel; the preset name is used only to keep the header readable.

`test_every_generator_carries_the_inspector_template_marker` fails if any
shipped generator loses the marker again. That test reads the DRP, so it covers
the built artifact rather than only the builder.

## Still open

The published `Font` and `Style` controls render as a broken pair: Resolve's
font control already draws family *and* style, so the panel shows
`Font / フォント` → `[Meiryo] [Regular]` followed by `Style / 書体` →
`[empty] [Bold]`. The style shown under Font is wrong and the empty dropdown is
noise. Publishing `Font` alone is the likely fix and needs its own Resolve check.
