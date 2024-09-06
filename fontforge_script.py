#!fontforge --lang=py -script

# 2つのフォントを合成する

import configparser
import math
import os
import shutil
import sys
import uuid
from decimal import ROUND_HALF_UP, Decimal

import fontforge
import psMat

# iniファイルを読み込む
settings = configparser.ConfigParser()
settings.read("build.ini", encoding="utf-8")

VERSION = settings.get("DEFAULT", "VERSION")
FONT_NAME = settings.get("DEFAULT", "FONT_NAME")
JP_FONT = settings.get("DEFAULT", "JP_FONT")
ENG_FONT = settings.get("DEFAULT", "ENG_FONT")
HACK_FONT = settings.get("DEFAULT", "HACK_FONT")
SOURCE_FONTS_DIR = settings.get("DEFAULT", "SOURCE_FONTS_DIR")
BUILD_FONTS_DIR = settings.get("DEFAULT", "BUILD_FONTS_DIR")
VENDER_NAME = settings.get("DEFAULT", "VENDER_NAME")
FONTFORGE_PREFIX = settings.get("DEFAULT", "FONTFORGE_PREFIX")
IDEOGRAPHIC_SPACE = settings.get("DEFAULT", "IDEOGRAPHIC_SPACE")
W35_WIDTH_STR = settings.get("DEFAULT", "W35_WIDTH_STR")
HIDDEN_ZENKAKU_SPACE_STR = settings.get("DEFAULT", "HIDDEN_ZENKAKU_SPACE_STR")
CONSOLE_STR = settings.get("DEFAULT", "CONSOLE_STR")
NERD_FONTS_STR = settings.get("DEFAULT", "NERD_FONTS_STR")
EM_ASCENT = int(settings.get("DEFAULT", "EM_ASCENT"))
EM_DESCENT = int(settings.get("DEFAULT", "EM_DESCENT"))
OS2_ASCENT = int(settings.get("DEFAULT", "OS2_ASCENT"))
OS2_DESCENT = int(settings.get("DEFAULT", "OS2_DESCENT"))
HALF_WIDTH_12 = int(settings.get("DEFAULT", "HALF_WIDTH_12"))
FULL_WIDTH_35 = int(settings.get("DEFAULT", "FULL_WIDTH_35"))

COPYRIGHT = """[0xProto]
Copyright (c) 2024, 0xType Project Authors https://github.com/0xType

[IBM Plex]
Copyright © 2017 IBM Corp. https://github.com/IBM/plex

[Hack]
Copyright 2018 Source Foundry Authors https://github.com/source-foundry/Hack

[Nerd Fonts]
Copyright (c) 2014, Ryan L McIntyre https://ryanlmcintyre.com

[explex]
Copyright 2024 Yuko Otawara
"""  # noqa: E501

options = {}
nerd_font = None


def main():
    # オプション判定
    get_options()
    if options.get("unknown-option"):
        usage()
        return

    # buildディレクトリを作成する
    if os.path.exists(BUILD_FONTS_DIR) and not options.get("do-not-delete-build-dir"):
        shutil.rmtree(BUILD_FONTS_DIR)
        os.mkdir(BUILD_FONTS_DIR)
    if not os.path.exists(BUILD_FONTS_DIR):
        os.mkdir(BUILD_FONTS_DIR)

    # Regular スタイルを生成する
    generate_font(
        jp_style="Text",
        eng_style="Regular",
        merged_style="Regular",
    )
    # Italic スタイルを生成する
    generate_font(
        jp_style="Text",
        eng_style="Italic",
        merged_style="Italic",
        italic=True,
    )

    # Bold スタイルを生成する
    generate_font(
        jp_style="Bold",
        eng_style="Bold",
        merged_style="Bold",
    )
    # Bold Italic スタイルを生成する
    generate_font(
        jp_style="Bold",
        eng_style="BoldItalic",
        merged_style="BoldItalic",
        italic=True,
    )


def usage():
    print(
        f"Usage: {sys.argv[0]} "
        "[--hidden-zenkaku-space] [--35] [--console] [--nerd-font]"
    )


def get_options():
    """オプションを取得する"""

    global options

    # オプションなしの場合は何もしない
    if len(sys.argv) == 1:
        return

    for arg in sys.argv[1:]:
        # オプション判定
        if arg == "--do-not-delete-build-dir":
            options["do-not-delete-build-dir"] = True
        elif arg == "--hidden-zenkaku-space":
            options["hidden-zenkaku-space"] = True
        elif arg == "--35":
            options["35"] = True
        elif arg == "--console":
            options["console"] = True
        elif arg == "--nerd-font":
            options["nerd-font"] = True
        else:
            options["unknown-option"] = True
            return


def generate_font(jp_style, eng_style, merged_style, italic=False):
    print(f"=== Generate {merged_style} ===")

    # 合成するフォントを開く
    jp_font, eng_font = open_fonts(jp_style, eng_style)

    # ※従来はEMをここで揃えるが、0xProto と IBM Plex Sans JP は既にEMが揃っているため不要

    # Hack フォントを優先するために不要なグリフを削除する
    delete_glyphs_prior_hack(jp_font, eng_font)
    # Hack フォントをマージする
    merge_hack(jp_font, eng_font, merged_style, italic)

    if options.get("console"):
        # コンソール用フォントの場合はできるだけEAAW文字を半角幅にする
        eaaw_width_to_half(jp_font)
    else:
        # 全角化する記号類を英語フォントから削除する
        delete_not_console_glyphs(eng_font)

    # 重複するグリフを削除する
    delete_duplicate_glyphs(jp_font, eng_font)

    # いくつかのグリフ形状に調整を加える
    adjust_some_glyph(jp_font, eng_font)

    # 日本語グリフの斜体を生成する
    if italic:
        if options.get("35"):
            transform_italic_glyphs(jp_font)
        else:
            # 英語フォントを1:2幅に縮めた際に傾斜が緩やかになるため合わせる
            transform_italic_glyphs(jp_font, italic_slope=8)

    # eng_fontを半角幅(600)にする
    width_600(eng_font)

    # jp_fontで半角幅(500)のグリフの幅を3:5になるよう調整する
    width_600_or_1000(jp_font)

    # 3:5幅版との差分を調整する
    if not options.get("35"):
        # 1:2 幅にする
        transform_half_width(jp_font, eng_font)
        # 規定の幅からはみ出したグリフサイズを縮小する
        down_scale_redundant_size_glyph(eng_font)

    # ひらがな等の全角文字が含まれる行でリガチャが解除される対策としてGSUBテーブルを削除
    # GPOSもおまけに削除
    remove_lookups(jp_font)

    # 全角スペースを可視化する
    if not options.get("hidden-zenkaku-space"):
        visualize_zenkaku_space(jp_font)

    # Nerd Fontのグリフを追加する
    if options.get("nerd-font"):
        add_nerd_font_glyphs(jp_font, eng_font)

    # オプション毎の修飾子を追加する
    variant = f"{CONSOLE_STR} " if options.get("console") else ""
    variant += HIDDEN_ZENKAKU_SPACE_STR if options.get("hidden-zenkaku-space") else ""
    variant += NERD_FONTS_STR if options.get("nerd-font") else ""
    variant = variant.strip()

    # macOSでのpostテーブルの使用性エラー対策
    # 重複するグリフ名を持つグリフをリネームする
    delete_glyphs_with_duplicate_glyph_names(eng_font)
    delete_glyphs_with_duplicate_glyph_names(jp_font)

    # メタデータを編集する
    cap_height = int(
        Decimal(str(eng_font[0x0048].boundingBox()[3])).quantize(
            Decimal("0"), ROUND_HALF_UP
        )
    )
    x_height = int(
        Decimal(str(eng_font[0x0078].boundingBox()[3])).quantize(
            Decimal("0"), ROUND_HALF_UP
        )
    )
    edit_meta_data(eng_font, merged_style, variant, cap_height, x_height)
    edit_meta_data(jp_font, merged_style, variant, cap_height, x_height)

    # ttfファイルに保存
    # なんらかフラグを立てるとGSUB, GPOSテーブルが削除されて後続の生成処理で影響が出るため注意
    w35_str = W35_WIDTH_STR if options.get("35") else ""
    eng_font.generate(
        f"{BUILD_FONTS_DIR}/{FONTFORGE_PREFIX}{FONT_NAME}{w35_str}{variant}-{merged_style}-eng.ttf".replace(
            " ", ""
        ),
    )
    jp_font.generate(
        f"{BUILD_FONTS_DIR}/{FONTFORGE_PREFIX}{FONT_NAME}{w35_str}{variant}-{merged_style}-jp.ttf".replace(
            " ", ""
        ),
    )

    # ttfを閉じる
    jp_font.close()
    eng_font.close()


def open_fonts(jp_style: str, eng_style: str):
    """フォントを開く"""
    jp_font = fontforge.open(f"{SOURCE_FONTS_DIR}/{JP_FONT}{jp_style}.ttf")
    if eng_style == "BoldItalic":
        # BoldItalic は自前生成のファイルを使用する
        eng_font = fontforge.open(f"{SOURCE_FONTS_DIR}/custom-0xProto-BoldItalic.ttf")
    else:
        eng_font = fontforge.open(f"{SOURCE_FONTS_DIR}/{ENG_FONT}{eng_style}.ttf")

    # fonttools merge エラー対処
    jp_font = altuni_to_entity(jp_font)

    # フォント参照を解除する
    for glyph in jp_font.glyphs():
        if glyph.isWorthOutputting():
            jp_font.selection.select(("more", None), glyph)
    jp_font.unlinkReferences()
    for glyph in eng_font.glyphs():
        if glyph.isWorthOutputting():
            eng_font.selection.select(("more", None), glyph)
    eng_font.unlinkReferences()

    return jp_font, eng_font


def altuni_to_entity(jp_font):
    """Alternate Unicodeで透過的に参照して表示している箇所を実体のあるグリフに変換する"""
    for glyph in jp_font.glyphs():
        if glyph.altuni is not None:
            # 以下形式のタプルで返ってくる
            # (unicode-value, variation-selector, reserved-field)
            # 第3フィールドは常に0なので無視
            altunis = glyph.altuni

            # variation-selectorがなく (-1)、透過的にグリフを参照しているものは実体のグリフに変換する
            before_altuni = ""
            for altuni in altunis:
                # 直前のaltuniと同じ場合はスキップ
                if altuni[1] == -1 and before_altuni != ",".join(map(str, altuni)):
                    glyph.altuni = None
                    copy_target_unicode = altuni[0]
                    try:
                        copy_target_glyph = jp_font.createChar(
                            copy_target_unicode,
                            f"uni{hex(copy_target_unicode).replace('0x', '').upper()}copy",
                        )
                    except Exception:
                        copy_target_glyph = jp_font[copy_target_unicode]
                    copy_target_glyph.clear()
                    copy_target_glyph.width = glyph.width
                    # copy_target_glyph.addReference(glyph.glyphname)
                    jp_font.selection.select(glyph.glyphname)
                    jp_font.copy()
                    jp_font.selection.select(copy_target_glyph.glyphname)
                    jp_font.paste()
                before_altuni = ",".join(map(str, altuni))
    # エンコーディングの整理のため、開き直す
    font_path = f"{BUILD_FONTS_DIR}/{jp_font.fullname}_{uuid.uuid4()}.ttf"
    jp_font.generate(font_path)
    jp_font.close()
    reopen_jp_font = fontforge.open(font_path)
    # 一時ファイルを削除
    os.remove(font_path)
    return reopen_jp_font


def add_nerd_font_glyphs(jp_font, eng_font):
    """Nerd Fontのグリフを追加する"""
    global nerd_font
    # Nerd Fontのグリフを追加する
    if nerd_font is None:
        nerd_font = fontforge.open(
            f"{SOURCE_FONTS_DIR}/nerd-fonts/SymbolsNerdFont-Regular.ttf"
        )
        nerd_font.em = EM_ASCENT + EM_DESCENT
        glyph_names = set()
        for nerd_glyph in nerd_font.glyphs():
            # Nerd Fontsのグリフ名をユニークにするため接尾辞を付ける
            nerd_glyph.glyphname = f"{nerd_glyph.glyphname}-nf"
            # postテーブルでのグリフ名重複対策
            # fonttools merge で合成した後、MacOSで `'post'テーブルの使用性` エラーが発生することへの対処
            if nerd_glyph.glyphname in glyph_names:
                nerd_glyph.glyphname = f"{nerd_glyph.glyphname}-{nerd_glyph.encoding}"
            glyph_names.add(nerd_glyph.glyphname)
            # 幅を調整する
            half_width = eng_font[0x0030].width
            # Powerline Symbols の調整
            if 0xE0B0 <= nerd_glyph.unicode <= 0xE0D4:
                # なぜかズレている右付きグリフの個別調整 (EM 1000 に変更した後を想定して調整)
                original_width = nerd_glyph.width
                if nerd_glyph.unicode == 0xE0B2:
                    nerd_glyph.transform(psMat.translate(-353, 0))
                elif nerd_glyph.unicode == 0xE0B6:
                    nerd_glyph.transform(psMat.translate(-414, 0))
                elif nerd_glyph.unicode == 0xE0C5:
                    nerd_glyph.transform(psMat.translate(-137, 0))
                elif nerd_glyph.unicode == 0xE0C7:
                    nerd_glyph.transform(psMat.translate(-214, 0))
                elif nerd_glyph.unicode == 0xE0D4:
                    nerd_glyph.transform(psMat.translate(-314, 0))
                nerd_glyph.width = original_width
                # 位置と幅合わせ
                if nerd_glyph.width < half_width:
                    nerd_glyph.transform(
                        psMat.translate((half_width - nerd_glyph.width) / 2, 0)
                    )
                elif nerd_glyph.width > half_width:
                    nerd_glyph.transform(psMat.scale(half_width / nerd_glyph.width, 1))
                # グリフの高さ・位置を調整する
                nerd_glyph.transform(psMat.scale(1, 1.14))
                nerd_glyph.transform(psMat.translate(0, 21))
            elif nerd_glyph.width < (EM_ASCENT + EM_DESCENT) * 0.6:
                # 幅が狭いグリフは中央寄せとみなして調整する
                nerd_glyph.transform(
                    psMat.translate((half_width - nerd_glyph.width) / 2, 0)
                )
            # 幅を設定
            nerd_glyph.width = half_width
    # 日本語フォントにマージするため、既に存在する場合は削除する
    for nerd_glyph in nerd_font.glyphs():
        if nerd_glyph.unicode != -1:
            # 既に存在する場合は削除する
            try:
                for glyph in jp_font.selection.select(
                    ("unicode", None), nerd_glyph.unicode
                ).byGlyphs:
                    glyph.clear()
            except Exception:
                pass
            try:
                for glyph in eng_font.selection.select(
                    ("unicode", None), nerd_glyph.unicode
                ).byGlyphs:
                    glyph.clear()
            except Exception:
                pass

    jp_font.mergeFonts(nerd_font)

    jp_font.selection.none()
    eng_font.selection.none()


def delete_glyphs_with_duplicate_glyph_names(font):
    """重複するグリフ名を持つグリフをリネームする"""
    glyph_name_set = set()
    for glyph in font.glyphs():
        if glyph.glyphname in glyph_name_set:
            glyph.glyphname = f"{glyph.glyphname}_{glyph.encoding}"
        else:
            glyph_name_set.add(glyph.glyphname)


def adjust_some_glyph(jp_font, eng_font):
    """いくつかのグリフ形状に調整を加える"""
    # 全角括弧の開きを広くする
    full_width = jp_font[0x3042].width
    for glyph_name in [0xFF08, 0xFF3B, 0xFF5B]:
        glyph = jp_font[glyph_name]
        glyph.transform(psMat.translate(-180, 0))
        glyph.width = full_width
    for glyph_name in [0xFF09, 0xFF3D, 0xFF5D]:
        glyph = jp_font[glyph_name]
        glyph.transform(psMat.translate(180, 0))
        glyph.width = full_width
    # LEFT SINGLE QUOTATION MARK (U+2018) ～ DOUBLE LOW-9 QUOTATION MARK (U+201E) の幅を全角幅にする
    for uni in range(0x2018, 0x201E + 1):
        try:
            glyph = jp_font[uni]
            glyph.transform(psMat.translate((full_width - glyph.width) / 2, 0))
            glyph.width = full_width
        except TypeError:
            # グリフが存在しない場合は継続する
            continue

    # 矢印記号の読みづらさ対策
    for uni in [*range(0x21CD, 0x21CF + 1), 0x21D0, 0x21D2, 0x21D4, 0x21DA, 0x21DB]:
        eng_font.selection.select(("unicode", None), uni)
        for glyph in eng_font.selection.byGlyphs:
            scale_glyph(glyph, 1, 1.3)
    for uni in [0x21D1, 0x21D3]:
        eng_font.selection.select(("unicode", None), uni)
        for glyph in eng_font.selection.byGlyphs:
            scale_glyph(glyph, 1.3, 1)
    for uni in range(0x21D6, 0x21D9 + 1):
        eng_font.selection.select(("unicode", None), uni)
        for glyph in eng_font.selection.byGlyphs:
            scale_glyph(glyph, 1.3, 1.3)

    jp_font.selection.none()
    eng_font.selection.none()


def em_1000(font):
    """フォントのEMを1000に変換する"""
    font.em = EM_ASCENT + EM_DESCENT


def delete_duplicate_glyphs(jp_font, eng_font):
    """jp_fontとeng_fontのグリフを比較し、重複するグリフを削除する"""

    eng_font.selection.none()
    jp_font.selection.none()

    for glyph in jp_font.glyphs("encoding"):
        try:
            if glyph.isWorthOutputting() and glyph.unicode > 0:
                eng_font.selection.select(("more", "unicode"), glyph.unicode)
        except ValueError:
            # Encoding is out of range のときは継続する
            continue
    for glyph in eng_font.selection.byGlyphs:
        # if glyph.isWorthOutputting():
        jp_font.selection.select(("more", "unicode"), glyph.unicode)
    for glyph in jp_font.selection.byGlyphs:
        glyph.clear()

    jp_font.selection.none()
    eng_font.selection.none()


def remove_lookups(font):
    """GSUB, GPOSテーブルを削除する"""
    for lookup in list(font.gsub_lookups) + list(font.gpos_lookups):
        font.removeLookup(lookup)


def transform_italic_glyphs(font, italic_slope=9):
    """斜体に変換する"""
    # 傾きを設定する
    font.italicangle = -italic_slope
    # 全グリフを斜体に変換
    for glyph in font.glyphs():
        glyph.transform(psMat.skew(italic_slope * math.pi / 180))


def delete_not_console_glyphs(eng_font):
    """日本語フォントを優先するために不要なグリフを削除する"""
    # TODO 内容精査
    eng_font.selection.none()

    # 記号
    eng_font.selection.select(("more", "unicode", "ranges"), 0x00A1, 0x00A5)
    eng_font.selection.select(("more", "unicode", "ranges"), 0x00A7, 0x00B8)
    eng_font.selection.select(("more", "unicode"), 0x00D7)
    eng_font.selection.select(("more", "unicode"), 0x00F7)
    eng_font.selection.select(("more", "unicode", "ranges"), 0x02BB, 0x02BC)
    eng_font.selection.select(("more", "unicode"), 0x02C6)
    eng_font.selection.select(("more", "unicode", "ranges"), 0x02DA, 0x02DC)
    # eng_font.selection.select(("more", "unicode", "ranges"), 0x0300, 0x0308)
    # eng_font.selection.select(("more", "unicode", "ranges"), 0x0310, 0x030C)
    # eng_font.selection.select(("more", "unicode", "ranges"), 0x0327, 0x0328)
    # ↑IBM Plex Sans JP でも630程度の幅だったため、半角扱いでも問題ないと判断
    eng_font.selection.select(("more", "unicode"), 0x0401)
    eng_font.selection.select(("more", "unicode", "ranges"), 0x0410, 0x044F)
    eng_font.selection.select(("more", "unicode"), 0x0451)
    eng_font.selection.select(("more", "unicode", "ranges"), 0x2010, 0x2026)
    eng_font.selection.select(("more", "unicode", "ranges"), 0x2030, 0x2044)
    eng_font.selection.select(("more", "unicode", "ranges"), 0x2113, 0x2116)
    eng_font.selection.select(("more", "unicode"), 0x2202)
    eng_font.selection.select(("more", "unicode", "ranges"), 0x2211, 0x222E)
    # 矢印
    eng_font.selection.select(("more", "unicode", "ranges"), 0x2190, 0x2193)
    eng_font.selection.select(("more", "unicode", "ranges"), 0x21C4, 0x21C6)
    eng_font.selection.select(("more", "unicode"), 0x21D2)
    eng_font.selection.select(("more", "unicode"), 0x21D4)
    eng_font.selection.select(("more", "unicode", "ranges"), 0x21E6, 0x21E9)
    eng_font.selection.select(("more", "unicode"), 0x21F5)
    # 数学記号
    eng_font.selection.select(("more", "unicode"), 0x2260)
    # 一部、英語フォントを適用する
    # 各エディタの可視化文字対策
    eng_font.selection.select(("less", "unicode"), 0x2022)
    eng_font.selection.select(("less", "unicode"), 0x00B7)
    eng_font.selection.select(("less", "unicode"), 0x2024)
    eng_font.selection.select(("less", "unicode"), 0x2219)
    eng_font.selection.select(("less", "unicode"), 0x25D8)
    eng_font.selection.select(("less", "unicode"), 0x25E6)
    # 結合文音記号は IBM Plex Mono を適用
    eng_font.selection.select(("less", "unicode", "ranges"), 0x0300, 0x0328)
    # IBM Plex Sans JP 等幅化対策 (IBM Plex Mono を適用して半角化)
    eng_font.selection.select(("less", "unicode"), 0xAB)
    eng_font.selection.select(("less", "unicode"), 0xBB)
    # flaction slash
    eng_font.selection.select(("less", "unicode"), 0x2044)
    # broken bar
    eng_font.selection.select(("less", "unicode"), 0x00A6)

    for glyph in eng_font.selection.byGlyphs:
        glyph.clear()

    eng_font.selection.none()


def delete_glyphs_prior_hack(jp_font, eng_font):
    """Hack フォントを優先するために不要なグリフを削除する"""
    if options.get("console"):
        # 矢印
        jp_font.selection.select(("more", "unicode", "ranges"), 0x2190, 0x21DD)
        jp_font.selection.select(("more", "unicode", "ranges"), 0x21E0, 0x21E9)
        jp_font.selection.select(("more", "unicode", "ranges"), 0x21EB, 0x21FF)
        eng_font.selection.select(("more", "unicode", "ranges"), 0x2190, 0x21DD)
        eng_font.selection.select(("more", "unicode", "ranges"), 0x21E0, 0x21E9)
        eng_font.selection.select(("more", "unicode", "ranges"), 0x21EB, 0x21FF)

    jp_font.selection.none()
    eng_font.selection.none()


def merge_hack(jp_font, eng_font, style, italic):
    """Hack フォントをマージする"""
    if "Bold" in style:
        if italic:
            hack_font = fontforge.open(
                f"{SOURCE_FONTS_DIR}/" + HACK_FONT.replace("{style}", "BoldItalic")
            )
        else:
            hack_font = fontforge.open(
                f"{SOURCE_FONTS_DIR}/" + HACK_FONT.replace("{style}", "Bold")
            )
    else:
        if italic:
            hack_font = fontforge.open(
                f"{SOURCE_FONTS_DIR}/" + HACK_FONT.replace("{style}", "Italic")
            )
        else:
            hack_font = fontforge.open(
                f"{SOURCE_FONTS_DIR}/" + HACK_FONT.replace("{style}", "Regular")
            )
    hack_font.em = EM_ASCENT + EM_DESCENT
    # 既に英語フォント側に存在する場合はhackグリフは削除する
    for glyph in eng_font.glyphs():
        if glyph.unicode != -1:
            try:
                for g in hack_font.selection.select(
                    ("unicode", None), glyph.unicode
                ).byGlyphs:
                    g.clear()
            except Exception:
                pass
    if options.get("console"):
        # Console版では、日本語フォントよりhackフォントのグリフを優先する
        for glyph in hack_font.glyphs():
            if glyph.unicode != -1:
                try:
                    for g in jp_font.selection.select(
                        ("unicode", None), glyph.unicode
                    ).byGlyphs:
                        g.clear()
                except Exception:
                    pass
    else:
        # 既に日本語フォント側に存在する場合はhackグリフは削除する
        for glyph in jp_font.glyphs():
            if glyph.unicode != -1:
                try:
                    for g in hack_font.selection.select(
                        ("unicode", None), glyph.unicode
                    ).byGlyphs:
                        g.clear()
                except Exception:
                    pass
    # EM 1000 にしたときの幅に合わせて調整
    half_width = int(FULL_WIDTH_35 * 3 / 5)
    for glyph in hack_font.glyphs():
        if glyph.width > 0:
            glyph.transform(psMat.translate((half_width - glyph.width) / 2, 0))
            glyph.width = half_width
    # Hack フォントをオブジェクトとして扱いたくないので、一旦ファイル保存して直接マージする
    font_path = f"{BUILD_FONTS_DIR}/tmp_hack_{uuid.uuid4()}.ttf"
    hack_font.generate(font_path)
    hack_font.close()

    eng_font.mergeFonts(font_path)
    os.remove(font_path)


def eaaw_width_to_half(jp_font):
    """East Asian Ambiguous Width 文字の半角化"""
    # ref: https://www.unicode.org/Public/15.1.0/ucd/EastAsianWidth.txt

    eaaw_unicode_list = (
        0x203B,  # REFERENCE MARK
        0x2103,
        0x2109,
        0x2121,
        0x212B,
        *range(0x2160, 0x216B + 1),
        *range(0x2170, 0x217B + 1),
        0x221F,
        0x222E,
        *range(0x226A, 0x226B + 1),
        0x22A5,
        0x22BF,
        0x2312,
        *range(0x2460, 0x2490 + 1),
        *range(0x249C, 0x24B5 + 1),
        *range(0x2605, 0x2606 + 1),
        0x260E,
        0x261C,
        0x261E,
        0x2640,
        0x2642,
        *range(0x2660, 0x2665 + 1),
        0x2667,
        0x266A,
        0x266D,
        0x266F,
        0x1F100,
    )
    half_width = jp_font[0x3042].width // 2
    for glyph in jp_font.glyphs():
        if glyph.unicode in eaaw_unicode_list and glyph.width > half_width:
            glyph.transform(psMat.translate((half_width - glyph.width) / 2, 0))
            glyph.width = half_width
            scale_glyph(glyph, 0.67, 0.9)


def width_600_or_1000(jp_font):
    """半角幅か全角幅になるように変換する"""
    for glyph in jp_font.glyphs():
        if 0 < glyph.width < 600:
            # グリフ位置を調整してから幅を設定
            glyph.transform(psMat.translate((600 - glyph.width) / 2, 0))
            glyph.width = 600
        elif 600 < glyph.width < 1000:
            # グリフ位置を調整してから幅を設定
            glyph.transform(psMat.translate((1000 - glyph.width) / 2, 0))
            glyph.width = 1000
        # 600の場合はそのまま


def width_600(eng_font):
    """英語フォントを半角幅になるように変換する"""
    mona_original_half_width = eng_font[0x0030].width
    after_width = 600
    x_scale = after_width / mona_original_half_width
    for glyph in eng_font.glyphs():
        if 0 < glyph.width < after_width:
            # after_width より幅が狭い場合は位置合わせしてから幅を設定
            glyph.transform(psMat.translate((after_width - glyph.width) / 2, 0))
            glyph.width = after_width
        elif after_width < glyph.width <= mona_original_half_width:
            # after_width より幅が広い、かつ元の半角幅より狭い場合は縮小してから幅を設定
            glyph.transform(psMat.scale(x_scale, 1))
            glyph.width = after_width
        elif mona_original_half_width < glyph.width:
            # after_width より幅が広い (おそらく全てリガチャ) の場合は600の倍数にする
            multiply_number = round(glyph.width / mona_original_half_width)
            glyph.transform(psMat.scale(x_scale, 1))
            glyph.width = after_width * multiply_number


def transform_half_width(jp_font, eng_font):
    """1:2幅になるように変換する。既に3:5幅になっていることを前提とする。"""
    before_width_eng = eng_font[0x0030].width
    after_width_eng = HALF_WIDTH_12
    # 最終的な設定幅に対してほんの少し広くなるように縮小する
    x_scale = HALF_WIDTH_12 * 1.048 / before_width_eng
    for glyph in eng_font.glyphs():
        if glyph.width > 0:
            # リガチャ考慮
            after_width_eng_multiply = after_width_eng * round(glyph.width / 600)
            # 縮小
            glyph.transform(psMat.scale(x_scale, 0.99))
            # 幅を設定
            glyph.transform(
                psMat.translate((after_width_eng_multiply - glyph.width) / 2, 0)
            )
            glyph.width = after_width_eng_multiply

    for glyph in jp_font.glyphs():
        if glyph.width == 600:
            # 英数字グリフと同じ幅にする
            glyph.transform(psMat.translate((after_width_eng - glyph.width) / 2, 0))
            glyph.width = after_width_eng
        elif glyph.width == 1000:
            # 全角は after_width_eng の倍の幅にする
            glyph.transform(psMat.translate((after_width_eng * 2 - glyph.width) / 2, 0))
            glyph.width = after_width_eng * 2


def down_scale_redundant_size_glyph(eng_font):
    """規定の幅からはみ出したグリフサイズを縮小する"""

    for glyph in eng_font.glyphs():
        xmin = glyph.boundingBox()[0]
        xmax = glyph.boundingBox()[2]

        if (
            glyph.width > 0
            and -15
            < xmin
            < 0  # 特定幅より左にはみ出している場合、意図的にはみ出しているものと見なして無視
            and abs(xmin) - 10
            < xmax - glyph.width
            < abs(xmin) + 10  # はみ出し幅が左側と右側で極端に異なる場合は無視
            and not (
                0x0020 <= glyph.unicode <= 0x02AF
            )  # latin 系のグリフ 0x0020 - 0x0192 は無視
            and not (
                0xE0B0 <= glyph.unicode <= 0xE0D4
            )  # Powerline系のグリフ 0xE0B0 - 0xE0D4 は無視
            and not (
                0x2500 <= glyph.unicode <= 0x257F
            )  # 罫線系のグリフ 0x2500 - 0x257F は無視
            and not (
                0x2591 <= glyph.unicode <= 0x2593
            )  # SHADE グリフ 0x2591 - 0x2593 は無視
        ):
            scale_glyph(glyph, 1 + (xmin / glyph.width) * 2, 1)


def scale_glyph(glyph, scale_x, scale_y):
    """グリフのスケールを調整する"""
    original_width = glyph.width
    # スケール前の中心位置を求める
    before_bb = glyph.boundingBox()
    before_center_x = (before_bb[0] + before_bb[2]) / 2
    before_center_y = (before_bb[1] + before_bb[3]) / 2
    # スケール変換
    glyph.transform(psMat.scale(scale_x, scale_y))
    # スケール後の中心位置を求める
    after_bb = glyph.boundingBox()
    after_center_x = (after_bb[0] + after_bb[2]) / 2
    after_center_y = (after_bb[1] + after_bb[3]) / 2
    # 拡大で増えた分を考慮して中心位置を調整
    glyph.transform(
        psMat.translate(
            before_center_x - after_center_x,
            before_center_y - after_center_y,
        )
    )
    glyph.width = original_width


def visualize_zenkaku_space(jp_font):
    """全角スペースを可視化する"""
    # 全角スペースを差し替え
    glyph = jp_font[0x3000]
    width_to = glyph.width
    glyph.clear()
    jp_font.mergeFonts(fontforge.open(f"{SOURCE_FONTS_DIR}/{IDEOGRAPHIC_SPACE}"))
    # 幅を設定し位置調整
    jp_font.selection.select("U+3000")
    for glyph in jp_font.selection.byGlyphs:
        width_from = glyph.width
        glyph.transform(psMat.translate((width_to - width_from) / 2, 0))
        glyph.width = width_to
    jp_font.selection.none()


def edit_meta_data(font, weight: str, variant: str, cap_height: int, x_height: int):
    """フォント内のメタデータを編集する"""
    font.ascent = EM_ASCENT
    font.descent = EM_DESCENT

    os2_ascent = OS2_ASCENT
    os2_descent = OS2_DESCENT

    font.os2_winascent = os2_ascent
    font.os2_windescent = os2_descent

    font.os2_typoascent = os2_ascent
    font.os2_typodescent = -os2_descent
    font.os2_typolinegap = 0

    font.hhea_ascent = os2_ascent
    font.hhea_descent = -os2_descent
    font.hhea_linegap = 0

    font.os2_xheight = x_height
    font.os2_capheight = cap_height

    # VSCode のターミナル上のボトム位置の表示で g, j などが見切れる問題への対処
    # 水平ベーステーブルを削除
    font.horizontalBaseline = None

    font.sfnt_names = (
        (
            "English (US)",
            "License",
            """This Font Software is licensed under the SIL Open Font License,
Version 1.1. This license is available with a FAQ
at: http://scripts.sil.org/OFL""",
        ),
        ("English (US)", "License URL", "http://scripts.sil.org/OFL"),
        ("English (US)", "Version", VERSION),
    )
    w35_str = W35_WIDTH_STR if options.get("35") else ""
    font.familyname = f"{FONT_NAME}{w35_str} {variant}".strip()
    font.fontname = f"{FONT_NAME}{w35_str}{variant}-{weight}"
    font.fullname = f"{FONT_NAME}{w35_str} {variant}".strip() + f" {weight}"
    font.os2_vendor = VENDER_NAME
    font.copyright = COPYRIGHT


if __name__ == "__main__":
    main()
