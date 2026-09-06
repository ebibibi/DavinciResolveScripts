"""Original Fusion title graphs; no downloaded macros or external media."""

import json


def literal(value: object) -> str:
    if isinstance(value, (tuple, list)):
        return "{ " + ", ".join(literal(v) for v in value) + " }"
    return json.dumps(value, ensure_ascii=False)


def node(name: str, kind: str, values: dict, links: dict | None = None) -> str:
    inputs = [
        f"{key} = Input {{ Value = {literal(value)}, }},"
        for key, value in values.items()
    ]
    inputs += [
        f'{key} = Input {{ SourceOp = "{op}", Source = "{port}", }},'
        for key, (op, port) in (links or {}).items()
    ]
    return f"{name} = {kind} {{ Inputs = {{\n" + "\n".join(inputs) + "\n}, },"


def text_node(
    name: str, text: str, size: float, center: list, color: list, outline: bool = False,
    font: str = "Meiryo", style: str = "Bold",
) -> str:
    values = {
        "Width": 1920,
        "Height": 1080,
        "UseFrameFormatSettings": 1,
        "StyledText": text,
        "Font": font,
        "Style": style,
        "Size": size,
        "Center": center,
        "VerticalJustificationNew": 3,
        "HorizontalJustificationNew": 3,
        "Red1": color[0],
        "Green1": color[1],
        "Blue1": color[2],
        "Enabled2": int(outline),
        "Appearance2": 1,
        "Thickness2": 0.025,
        "Red2": 0,
        "Green2": 0,
        "Blue2": 0,
        "Enabled3": 0,
        "Enabled4": 0,
    }
    return node(name, "TextPlus", values)


def title_macro(preset: dict) -> str:
    """Publish one small Inspector, including a global position/scale control."""
    parts = [
        text_node(
            "MainText",
            preset["text"],
            preset["size"],
            preset["center"],
            preset["color"],
            preset.get("outline", False),
            preset.get("font", "Meiryo"),
            preset.get("style", "Bold"),
        )
    ]
    last = "MainText"
    if "box" in preset:
        x, y, width, height = preset["box"]
        parts += [
            node(
                "CardMask",
                "RectangleMask",
                {
                    "MaskWidth": 1920,
                    "MaskHeight": 1080,
                    "PixelAspect": [1, 1],
                    "UseFrameFormatSettings": 1,
                    "Center": [x, y],
                    "Width": width,
                    "Height": height,
                    "CornerRadius": preset.get("corner_radius", 0.025),
                },
            ),
            node(
                "Card",
                "Background",
                {
                    "Width": 1920,
                    "Height": 1080,
                    "UseFrameFormatSettings": 1,
                    "TopLeftRed": preset["background"][0],
                    "TopLeftGreen": preset["background"][1],
                    "TopLeftBlue": preset["background"][2],
                    "TopLeftAlpha": preset.get("opacity", 0.9),
                },
                {"EffectMask": ("CardMask", "Mask")},
            ),
            node(
                "MainOnCard",
                "Merge",
                {"PerformDepthMerge": 0},
                {
                    "Background": ("Card", "Output"),
                    "Foreground": ("MainText", "Output"),
                },
            ),
        ]
        last = "MainOnCard"
    if preset.get("subtitle"):
        parts += [
            text_node(
                "SubText",
                preset["subtitle"],
                preset["subsize"],
                preset["subcenter"],
                preset.get("subcolor", [1, 1, 1]),
                font=preset.get("subfont", preset.get("font", "Meiryo")),
                style=preset.get("substyle", preset.get("style", "Bold")),
            ),
            node(
                "WithSubtitle",
                "Merge",
                {"PerformDepthMerge": 0},
                {"Background": (last, "Output"), "Foreground": ("SubText", "Output")},
            ),
        ]
        last = "WithSubtitle"
    parts += [
        node(
            "Placement",
            "Transform",
            {"Center": [0.5, 0.5], "Size": 1},
            {"Input": (last, "Output")},
        )
    ]
    controls = [
        ("StyledText", "MainText", "StyledText", "Text / 本文"),
        ("Font", "MainText", "Font", "Font / フォント"),
        ("Style", "MainText", "Style", "Style / 書体"),
        ("Size", "MainText", "Size", "Text size / 文字サイズ"),
        ("Red1", "MainText", "Red1", "Text color / 文字色"),
        ("Green1", "MainText", "Green1", None),
        ("Blue1", "MainText", "Blue1", None),
        ("Center", "Placement", "Center", "Position / 全体の位置"),
        ("Scale", "Placement", "Size", "Scale / 全体の大きさ"),
    ]
    if preset.get("subtitle"):
        controls += [
            ("SubText", "SubText", "StyledText", "Second line / 補足"),
            ("SubFont", "SubText", "Font", "Second font / 補足フォント"),
            ("SubStyle", "SubText", "Style", "Second style / 補足書体"),
            ("SubSize", "SubText", "Size", "Second size / 補足サイズ"),
        ]
    if "box" in preset:
        controls += [
            ("CardRed", "Card", "TopLeftRed", "Band color / 帯の色"),
            ("CardGreen", "Card", "TopLeftGreen", None),
            ("CardBlue", "Card", "TopLeftBlue", None),
            ("CardAlpha", "Card", "TopLeftAlpha", "Band opacity / 帯の濃さ"),
            ("CardWidth", "CardMask", "Width", "Band width / 帯の幅"),
            ("CardHeight", "CardMask", "Height", "Band height / 帯の高さ"),
        ]
    published = []
    for key, op, source, label in controls:
        label_text = f"Name = {literal(label)}, " if label else ""
        color_group = "ControlGroup = 1, " if key in ("Red1", "Green1", "Blue1") else ""
        if key in ("CardRed", "CardGreen", "CardBlue", "CardAlpha"):
            color_group = "ControlGroup = 2, "
        published.append(
            f'{key} = InstanceInput {{ {label_text}{color_group}SourceOp = "{op}", Source = "{source}", }},'
        )
    return (
        "Template = MacroOperator {\nInputs = ordered() {\n"
        + "\n".join(published)
        + '\n},\nOutputs = { MainOutput1 = InstanceOutput { SourceOp = "Placement", Source = "Output", }, },\n'
        + "Tools = ordered() {\n"
        + "\n".join(parts)
        + "\n},\n},"
    )


def setting_text(preset: dict) -> str:
    return (
        "{ Tools = ordered() {\n"
        + title_macro(preset)
        + '\n}, ActiveTool = "Template", }\n'
    )


def composition_tools(preset: dict) -> str:
    return (
        "{\n"
        + title_macro(preset)
        + "\n"
        + node(
            "MediaOut1",
            "MediaOut",
            {"Index": "0"},
            # Resolve 20 serializes a macro connection using the underlying
            # tool, even though FindMainOutput(1) exposes MainOutput1. Using
            # the macro alias here silently imports with a disconnected input.
            {"Input": ("Placement", "Output")},
        )
        + "\n}\0"
    )
