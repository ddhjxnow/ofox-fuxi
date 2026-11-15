#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 OrangeFox 自带主题的"声明分辨率"改成目标机型的真实分辨率。

为什么需要这一步（机制）：
  bootable/recovery/gui/pages.cpp 的 PageSet::LoadDetails() 会读 theme 里
  <resolution width=... height=...> 的值，然后算
      scale_w = fb_width  / 声明宽度
      scale_h = fb_height / 声明高度
  并按这两个比例分别缩放整个 UI。
  OrangeFox 只带 portrait_hdpi 一套主题，声明的是 1080x1920。
  小米13 (fuxi) 是 1080x2400，于是 scale_w=1.0、scale_h=(2400-99)/1920≈1.20：
  横竖缩放不一致 → 界面被纵向拉长、控件错位。
  把声明值改成 1080x2400 后 scale_w=scale_h=1.0，UI 才是 1:1 的原生像素。

用法: python3 fix_ofox_theme.py <recovery源码根目录> [宽] [高]
例如: python3 fix_ofox_theme.py fox_12.1 1080 2400
"""
import re
import sys
import os

THEME_DIR = "gui/theme/portrait_hdpi"
UI_XML = os.path.join(THEME_DIR, "ui.xml")
SPLASH_XML = os.path.join(THEME_DIR, "splash.xml")


def read(path):
    with open(path, "r", encoding="utf-8", errors="surrogateescape") as f:
        return f.read()


def write(path, data):
    with open(path, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(data)


def patch_resolution_tag(text, width, height, height_attr):
    """把 <resolution width=".." h|height=".." /> 里的两个数字换掉，保留其余属性。"""
    pattern = re.compile(
        r'(<resolution\b[^>]*\bwidth=")(\d+)("[^>]*\b' + height_attr + r'=")(\d+)(")'
    )

    def repl(m):
        old = m.group(0)
        if m.group(2) == str(width) and m.group(4) == str(height):
            return old
        return m.group(1) + str(width) + m.group(3) + str(height) + m.group(5)

    new, n = pattern.subn(repl, text)
    return new, n


def main():
    if len(sys.argv) < 2:
        print("usage: fix_ofox_theme.py <recovery_src_root> [width] [height]")
        return 2
    root = os.path.abspath(sys.argv[1])
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 1080
    height = int(sys.argv[3]) if len(sys.argv) > 3 else 2400

    ui = os.path.join(root, UI_XML)
    splash = os.path.join(root, SPLASH_XML)
    for p in (ui, splash):
        if not os.path.exists(p):
            print("ERROR: 找不到 %s（确认 %s 是 OrangeFox 源码根目录、分支正确）" % (p, root))
            return 1

    changed = []

    # ui.xml: <resolution width="1080" height="1920" />
    data = read(ui)
    new, n = patch_resolution_tag(data, width, height, "height")
    if n == 0:
        print("WARN: ui.xml 里没匹配到 <resolution ...> 标签，跳过")
    if new != data:
        write(ui, new)
        changed.append(ui)

    # splash.xml: <resolution width="1080" h="1920"/> + <variable name="screen_height" value="1920"/>
    data = read(splash)
    new, n = patch_resolution_tag(data, width, height, "h")
    if n == 0:
        print("WARN: splash.xml 里没匹配到 <resolution ...> 标签，跳过")
    new = re.sub(
        r'(<variable\s+name="screen_height"\s+value=")(\d+)(")',
        lambda m: m.group(1) + str(height) + m.group(3),
        new,
    )
    new = re.sub(
        r'(<variable\s+name="screen_width"\s+value=")(\d+)(")',
        lambda m: m.group(1) + str(width) + m.group(3),
        new,
    )
    if new != data:
        write(splash, new)
        changed.append(splash)

    # mifs（小米私有 f2fs 变体）支持：R11.3 之后上游已内置，这里只做检查
    part = os.path.join(root, "partition.cpp")
    if os.path.exists(part):
        if '"mifs"' in read(part):
            print("OK   partition.cpp 已含 mifs 支持，无需打 patch")
        else:
            print("WARN partition.cpp 不含 mifs，HyperOS2/mifs 加密的 /data 可能无法解密")

    if changed:
        for c in changed:
            print("修改:", c)
    else:
        print("OK   主题分辨率已经是 %dx%d，无需修改（幂等）" % (width, height))

    # 回显结果，方便在 CI 日志里核对
    for p in (ui, splash):
        for line in read(p).splitlines():
            if "<resolution" in line or "screen_height" in line:
                print("  %-9s %s" % (os.path.basename(p), line.strip()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
