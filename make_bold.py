import configparser

import fontforge

settings = configparser.ConfigParser()
settings.read("build.ini", encoding="utf-8")
SOURCE_FONTS_DIR = settings.get("DEFAULT", "SOURCE_FONTS_DIR")


def main():
    font = fontforge.open(f"{SOURCE_FONTS_DIR}/0xProto/0xProto-Italic.ttf")

    print("***** BoldItalic用の太字フォントを作成します *****")

    for i, glyph in enumerate(font.glyphs()):
        if i % 100 == 0:
            print(f"{i}文字目を処理中")
        if glyph.isWorthOutputting():
            glyph.stroke(
                "circular",
                36,
                "nib",
                "miter",
                removeinternal=True,
                removeoverlap="none",
            )
            glyph.removeOverlap()

    # ttfファイルを保存
    font.generate(f"{SOURCE_FONTS_DIR}/custom-0xProto-BoldItalic.ttf")


if __name__ == "__main__":
    main()
