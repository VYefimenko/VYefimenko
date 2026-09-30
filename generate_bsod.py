#!/usr/bin/env python3
"""Builds assets/bsod-{dark,light}.svg: the live contribution graph freezes,
drags a trail of "Not Responding" dialogs, blue-screens, and reboots through a
90s BIOS POST that reports the graph's contribution stats.

Usage: python generate_bsod.py [login]
"""
import os
from datetime import timedelta

from generate import (BOX_H, BOX_Y, CELL, FONT, GRID_X, GRID_Y, H, LOGIN, MONO, PITCH, THEMES, W, T,
                      Anim, fetch, fmt)

WIN = "Tahoma,'MS Sans Serif','Segoe UI',sans-serif"
BSOD_BLUE, VGA_GRAY = "#0000aa", "#aaaaaa"
DLG_X, DLG_Y, DLG_DX, DLG_DY, TRAIL = 90, 34, 14, 6, 19


def stats(counts):
    days = sorted(counts)
    best_day = max(days, key=lambda d: counts[d])
    longest = run = 0
    for d in days:
        run = run + 1 if counts[d] else 0
        longest = max(longest, run)
    current, d = 0, days[-1] if counts[days[-1]] else days[-1] - timedelta(days=1)
    while d in counts and counts[d]:
        current, d = current + 1, d - timedelta(days=1)
    return longest, (counts[best_day], best_day), current


def dialog():
    """Win9x 'Not Responding' box, 300x112, drawn at the origin."""
    bevel = lambda x, y, w, h: (f'<path d="M{x} {y + h}V{y}H{x + w}" stroke="#fff"/>'
                                f'<path d="M{x} {y + h}H{x + w}V{y}" stroke="#404040"/>')
    return (f'<g id="dlg"><rect width="300" height="112" fill="#c0c0c0"/>{bevel(.5, .5, 299, 111)}'
            f'<rect x="3" y="3" width="294" height="18" fill="url(#title)"/>'
            f'<text x="8" y="16" font-family="{WIN}" font-size="11" font-weight="700" fill="#fff">contributions.exe</text>'
            f'<rect x="279" y="5" width="15" height="14" fill="#c0c0c0"/>{bevel(279.5, 5.5, 14, 13)}'
            f'<path d="M283 9l7 6M290 9l-7 6" stroke="#000" stroke-width="1.6"/>'
            f'<circle cx="32" cy="52" r="14" fill="#f00" stroke="#800000"/><path d="M26 46l12 12M38 46l-12 12" stroke="#fff" stroke-width="3"/>'
            f'<text x="58" y="48" font-family="{WIN}" font-size="12" fill="#000">contributions.exe is not responding.</text>'
            f'<text x="58" y="64" font-family="{WIN}" font-size="11" fill="#000">Close it and you may lose unsaved commits.</text>'
            + "".join(f'<rect x="{x}" y="80" width="80" height="22" fill="#c0c0c0"/>{bevel(x + .5, 80.5, 79, 21)}'
                      f'<text x="{x + 40}" y="95" font-family="{WIN}" font-size="11" fill="#000" text-anchor="middle">{label}</text>'
                      for x, label in ((116, "End Task"), (204, "Wait")))
            + '<rect x="120" y="84" width="72" height="14" stroke="#000" stroke-dasharray="1 1"/></g>')


def build(theme, total, days, counts):
    c = THEMES[theme]
    A = Anim()
    out = []
    o = out.append
    longest, (best_n, best_d), current = stats(counts)

    # ---------- the graph ----------
    o(f'<g {A.windows([(0, 5.7), (12.6, T)])}>')
    o(f'<text x="0" y="17" font-size="16" fill="{c["fg"]}" {A.windows([(0, 4.0), (12.6, T)])}>{fmt(total)}</text>')
    o(f'<text x="0" y="17" font-size="16" fill="{c["fg"]}" {A.windows([(4.0, 5.7)])}>{fmt(total)} (Not Responding)</text>')
    o(f'<rect x=".5" y="{BOX_Y + .5}" width="{W - 1}" height="{BOX_H}" rx="6" stroke="{c["border"]}"/>')
    last_col = -9
    for col in range(max(d[0] for d in days) + 1):
        firsts = [d for d in days if d[0] == col and d[2].day == 1]
        if firsts and col - last_col >= 2:
            o(f'<text x="{GRID_X + col * PITCH}" y="62" font-size="12" fill="{c["fg"]}">{firsts[0][2].strftime("%b")}</text>')
            last_col = col
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        o(f'<text x="36" y="{GRID_Y + row * PITCH + 9}" font-size="12" fill="{c["fg"]}">{name}</text>')
    fy = BOX_Y + BOX_H - 13
    o(f'<text x="41" y="{fy}" font-size="12" fill="{c["muted"]}">Learn how we count contributions</text>'
      f'<text x="855" y="{fy}" font-size="12" fill="{c["muted"]}" text-anchor="end">More</text>'
      f'<text x="{823 - CELL - 60}" y="{fy}" font-size="12" fill="{c["muted"]}" text-anchor="end">Less</text>')
    for i in range(5):
        o(f'<rect x="{823 - CELL - 14 * (4 - i)}" y="{fy - 10}" width="{CELL}" height="{CELL}" rx="2" '
          f'fill="{c["cells"][i]}" stroke="{c["cell_border"]}" stroke-width=".5"/>')
    # After the reboot the squares redraw column by column.
    pops = {}
    for col, row, _, lvl in days:
        if col not in pops:
            s = 12.7 + col * .016
            pops[col] = A.add([(0, "transform:scale(1)"), (12.5, "transform:scale(1)"), (12.55, "transform:scale(0)"),
                               (s, "transform:scale(0)", "cubic-bezier(.3,1.6,.5,1)"), (s + .35, "transform:scale(1)"),
                               (T, "transform:scale(1)")])
        o(f'<g transform="translate({GRID_X + col * PITCH},{GRID_Y + row * PITCH})"><rect class="fx" width="{CELL}" '
          f'height="{CELL}" rx="2" fill="{c["cells"][lvl]}" stroke="{c["cell_border"]}" stroke-width=".5" {pops[col]}/></g>')
    ghost = ".22" if theme == "dark" else ".5"
    o(f'<rect y="{BOX_Y}" width="{W}" height="{BOX_H + 1}" rx="6" fill="#fff" opacity="0" '
      f'{A.add([(0, "opacity:0"), (3.9, "opacity:0"), (4.5, f"opacity:{ghost}"), (5.69, f"opacity:{ghost}"), (5.7, "opacity:0"), (T, "opacity:0")])}/>')
    o("</g>")

    # ---------- frozen window + drag trail ----------
    o(f'<use href="#dlg" x="{DLG_X}" y="{DLG_Y}" opacity="0" {A.windows([(4.1, 5.7)])}/>')
    for k in range(1, TRAIL + 1):
        o(f'<use href="#dlg" x="{DLG_X + DLG_DX * k}" y="{DLG_Y + DLG_DY * k}" opacity="0" '
          f'{A.windows([(4.5 + k * .055, 5.7)])}/>')
    grab = lambda k: f"transform:translate({DLG_X + 150 + DLG_DX * k}px,{DLG_Y + 11 + DLG_DY * k}px)"
    park = "transform:translate(760px,190px)"
    path = [(0, park), (3.6, park, "cubic-bezier(.4,0,.2,1)"), (4.3, grab(0))]
    path += [(4.5 + k * .055, grab(k), "steps(1,end)") for k in range(1, TRAIL + 1)]
    path += [(5.7, grab(TRAIL)), (T, park)]
    o(f'<g opacity="0" {A.windows([(3.6, 5.7)])}><path d="M0 0v16l4-4 3.5 7 2.2-1-3.4-7H11z" fill="#fff" stroke="#000" '
      f'stroke-linejoin="round" {A.add(path)}/></g>')

    # ---------- blue screen ----------
    lines = [(72, "A fatal exception 0E has occurred at 0028:C0DE1337 in VXD GRAPH(01) +"),
             (89, "00000539. The current contribution graph will be terminated."),
             (120, "*  Press any key to terminate the current application."),
             (137, "*  Press CTRL+ALT+DEL again to restart your profile. You will"),
             (154, "   lose any unsaved commits in all applications.")]
    o(f'<g opacity="0" {A.windows([(5.7, 7.6)])}><rect width="{W}" height="{H}" rx="6" fill="{BSOD_BLUE}"/>'
      f'<rect x="{W / 2 - 36}" y="30" width="72" height="17" fill="{VGA_GRAY}"/>'
      f'<text x="{W / 2}" y="43" font-family="{MONO}" font-size="13" font-weight="700" fill="{BSOD_BLUE}" text-anchor="middle">GitHub</text>'
      + "".join(f'<text x="152" y="{y}" font-family="{MONO}" font-size="13" fill="#fff" xml:space="preserve">{t}</text>' for y, t in lines)
      + f'<text x="{W / 2}" y="192" font-family="{MONO}" font-size="13" fill="#fff" text-anchor="middle">'
        f'Press any key to continue <tspan class="blink">_</tspan></text></g>')

    # ---------- reboot: BIOS POST ----------
    o(f'<g opacity="0" {A.windows([(7.6, 12.6)])}><rect width="{W}" height="{H}" rx="6" fill="#000"/>'
      f'<text x="24" y="24" font-family="{MONO}" font-size="12" fill="{VGA_GRAY}" {A.windows([(7.6, 8.1)])}>'
      f'<tspan class="blink">_</tspan></text></g>')
    post = f'<g font-family="{MONO}" font-size="12" fill="{VGA_GRAY}" xml:space="preserve" opacity="0" {A.windows([(8.1, 12.4)])}>'
    # Logo: the last 7 weeks of the graph.
    c0 = max(d[0] for d in days) - 6
    for col, row, _, lvl in (d for d in days if d[0] >= c0):
        post += (f'<rect x="{806 + (col - c0) * 9}" y="{12 + row * 9}" width="7" height="7" rx="1" '
                 f'fill="{THEMES["dark"]["cells"][lvl] if lvl else "#1a1a1a"}"/>')
    post += f'<text x="{806 + 31}" y="86" font-size="9" text-anchor="middle" fill="#fff">GRAPH</text>'
    post += f'<text x="24" y="22" fill="#fff">{LOGIN} Modular BIOS v4.20, An Energy Star Ally</text>'
    post += '<text x="24" y="37">Copyright (C) 1998-2026, Contribution Megatrends, Inc.</text>'
    post += f'<text x="24" y="58" {A.windows([(8.35, T)])}>Main Processor : Human, 1 core @ 3.00GHz (coffee-cooled)</text>'
    mem = [1024 * 2 ** k for k in range(7)] + [65536]
    for k, kb in enumerate(mem):
        a = 8.5 + k * .11
        end = a + .11 if k < len(mem) - 1 else T
        tail = " OK" if k == len(mem) - 1 else ""
        post += f'<text x="24" y="73" {A.windows([(a, end)])}>Memory Testing : {kb:>6}K{tail}</text>'
    report = [(94, "Detecting Contributions ...... ", f"{total:,} found", 9.6),
              (109, "Longest Streak ............... ", f"{longest} day{'s' if longest != 1 else ''}", 10.1),
              (124, "Best Day ..................... ",
               f"{best_n} contribution{'s' if best_n != 1 else ''}" + (f" ({best_d:%b %d})" if best_n else ""), 10.5),
              (139, "Current Streak ............... ", f"{current} day{'s' if current != 1 else ''}", 10.9)]
    for y, label, value, a in report:
        post += (f'<text x="24" y="{y}" {A.windows([(a, T)])}>{label}<tspan fill="#fff" '
                 f'{A.windows([(a + .25, T)], prop="fill-opacity")}>{value}</tspan></text>')
    post += f'<g {A.windows([(11.3, T)])}><text x="24" y="165">Loading graph  [</text>'
    bar = [(0, "transform:scaleX(0)")] + [(11.3 + k * .05, f"transform:scaleX({k / 20:g})") for k in range(21)]
    post += f'<rect class="fxl" x="150" y="156" width="300" height="10" fill="{VGA_GRAY}" {A.add(bar + [(T, "transform:scaleX(1)")], steps=True)}/>'
    post += '<text x="452" y="165">]</text>'
    for k in range(11):
        a = 11.3 + k * .1
        post += f'<text x="466" y="165" {A.windows([(a, a + .1 if k < 10 else T)])}>{k * 10:>3}%</text>'
    post += "</g>"
    post += '<text x="24" y="206">Press DEL to enter SETUP, ESC to skip memory test</text>'
    post += f'<text x="{W - 24}" y="206" text-anchor="end">{max(counts):%m/%d/%Y}-GH-PROFILE-4.20</text></g>'
    o(post)

    defs = (f'<defs><linearGradient id="title" x1="0" x2="1"><stop offset="0" stop-color="#000080"/>'
            f'<stop offset="1" stop-color="#1084d0"/></linearGradient>{dialog()}</defs>')
    css = ("<style>.fx{transform-box:fill-box;transform-origin:center}.fxl{transform-box:fill-box;transform-origin:left center}"
           ".blink{animation:bl 1s steps(1,end) infinite}@keyframes bl{50%%{fill-opacity:0}}%s</style>" % "".join(A.css))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none" '
            f'font-family="{FONT}">{css}{defs}{"".join(out)}</svg>')


def main():
    total, days, counts = fetch()
    os.makedirs("assets", exist_ok=True)
    for theme in THEMES:
        path = f"assets/bsod-{theme}.svg"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(build(theme, total, days, counts))
        print(f"{path}: {os.path.getsize(path) // 1024} KB")


if __name__ == "__main__":
    main()
