#!/usr/bin/env python3
"""Builds assets/glitch-{dark,light}.svg: a pixel-accurate copy of the GitHub
contribution graph (with real data) that glitches, collapses and reveals a
hidden scene. Pure CSS animation, no JS, so it survives GitHub's image proxy.

Usage: python generate.py [login]   (token: $GITHUB_TOKEN or `gh auth token`)
"""
import json
import math
import os
import random
import subprocess
import sys
import urllib.request
from datetime import date
from html import escape

LOGIN = os.environ.get("LOGIN") or (sys.argv[1] if len(sys.argv) > 1 else "VYefimenko")
T = 16.0          # full cycle, seconds
W, H = 896, 220   # native width of the profile main column
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
JP = "'Yu Gothic','Hiragino Sans','Noto Sans JP','Noto Sans CJK JP',Meiryo,sans-serif"

# Exact values from GitHub's primer CSS.
THEMES = {
    "dark": dict(fg="#f0f6fc", muted="#9198a1", border="#3d444d", cell_border="#0104090d",
                 cells=["#151b23", "#033a16", "#196c2e", "#2ea043", "#56d364"],
                 flash_bg="#f851491a", flash_border="#f8514966", danger="#f85149"),
    "light": dict(fg="#1f2328", muted="#59636e", border="#d1d9e0", cell_border="#1f23280d",
                  cells=["#eff2f5", "#aceebb", "#4ac26b", "#2da44e", "#116329"],
                  flash_bg="#ffebe9", flash_border="#ff818266", danger="#d1242f"),
}
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

# Geometry measured from the live profile page.
GRID_X, GRID_Y, PITCH, CELL = 69, 73, 15, 11
BOX_Y, BOX_H = 32, 179


def token():
    return os.environ.get("GITHUB_TOKEN") or subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def fetch():
    q = ('{user(login:"%s"){contributionsCollection{contributionCalendar{totalContributions '
         'weeks{contributionDays{date contributionLevel}}}}}}' % LOGIN)
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=json.dumps({"query": q}).encode(),
        headers={"Authorization": "bearer " + token(), "Content-Type": "application/json"})
    cal = json.load(urllib.request.urlopen(req))["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = []
    for col, week in enumerate(cal["weeks"]):
        for d in week["contributionDays"]:
            dt = date.fromisoformat(d["date"])
            days.append((col, (dt.weekday() + 1) % 7, dt, LEVELS[d["contributionLevel"]]))
    return cal["totalContributions"], days


def pct(t):
    return f"{t / T * 100:.3f}".rstrip("0").rstrip(".") + "%"


class Anim:
    """Collects unique @keyframes; every animation runs on the same 16s clock."""

    def __init__(self):
        self.css, self.n = [], 0

    def add(self, frames, steps=False):
        """frames: [(t, decls[, easing])]; returns an inline style string."""
        self.n += 1
        name = f"k{self.n}"
        body = ""
        for f in frames:
            t, decl = f[0], f[1]
            ease = f";animation-timing-function:{f[2]}" if len(f) > 2 else ""
            body += f"{pct(t)}{{{decl}{ease}}}"
        self.css.append(f"@keyframes {name}{{{body}}}")
        timing = " steps(1,end)" if steps else ""
        return f'style="animation:{name} {T:g}s{timing} infinite"'

    def windows(self, wins, prop="opacity", on="1", off="0"):
        """Discrete visibility during [(start, end), ...]."""
        first = on if wins and wins[0][0] == 0 else off
        frames = [(0, f"{prop}:{first}")]
        for a, b in wins:
            if a > 0:
                frames.append((a, f"{prop}:{on}"))
            frames.append((b, f"{prop}:{off}"))
        frames.append((T, f"{prop}:{first}"))
        return self.add(frames, steps=True)

    def fall(self, start, rnd, heavy=False):
        """Hop, drop out of frame with spin, then rewind into place at loop end."""
        dx = rnd.uniform(-60, 60) if not heavy else rnd.uniform(-20, 20)
        rot = rnd.uniform(-240, 240) if not heavy else rnd.uniform(-9, 9)
        dy = H + 60 + rnd.uniform(0, 80)
        hop = f"transform:translate({dx * .06:.1f}px,-7px) rotate({rot * .04:.1f}deg)"
        down = f"transform:translate({dx:.1f}px,{dy:.0f}px) rotate({rot:.0f}deg)"
        home = "transform:translate(0,0) rotate(0)"
        return self.add([
            (0, home), (start, home, "cubic-bezier(.3,0,.6,1)"),
            (start + .14, hop, "cubic-bezier(.55,0,.95,.55)"),
            (start + .14 + rnd.uniform(.75, 1.0), down),
            (15.6, down, "cubic-bezier(.2,.9,.25,1)"), (T, home)])


def fmt(n):
    return f"{n:,} contribution{'s' if n != 1 else ''} in the last year"


def build(theme, total, days):
    c = THEMES[theme]
    rnd = random.Random(1337)
    A = Anim()
    out = []
    o = out.append
    ncols = max(d[0] for d in days) + 1

    # ---------- the fake card ----------
    jitter = [(0, "transform:translate(0,0)"), (3.3, "transform:translate(-4px,0)"),
              (3.36, "transform:translate(2px,0)"), (3.42, "transform:translate(0,0)")]
    t = 4.4
    while t < 5.0:
        jitter.append((t, f"transform:translate({rnd.uniform(-6, 6):.1f}px,{rnd.uniform(-2, 2):.1f}px) "
                          f"skewX({rnd.uniform(-4, 4):.1f}deg)"))
        t += .05
    jitter += [(5.0, "transform:translate(0,3px)"), (5.08, "transform:translate(0,0)"), (T, "transform:translate(0,0)")]
    o(f'<g {A.add(jitter, steps=True)}>')

    # Heading: real count, then it spins up to 999,999,999 with corrupt flashes.
    head = f'<g class="fx" {A.fall(6.1, rnd, heavy=True)}>'
    real = max(total, 1)
    seq = [int(real * (999_999_999 / real) ** (i / 10)) for i in range(1, 10)]
    head += f'<text x="0" y="17" font-size="16" fill="{c["fg"]}" {A.windows([(0, 3.5), (15.6, T)])}>{fmt(total)}</text>'
    for i, v in enumerate(seq):
        a = 3.5 + i * .1
        head += f'<text x="0" y="17" font-size="16" fill="{c["fg"]}" {A.windows([(a, a + .1)])}>{fmt(v)}</text>'
    big = fmt(999_999_999)
    head += f'<text x="0" y="17" font-size="16" fill="{c["fg"]}" {A.windows([(4.4, 4.72), (4.82, 5.0), (5.06, 15.6)])}>{big}</text>'
    head += f'<text x="0" y="17" font-size="16" fill="{c["danger"]}" {A.windows([(4.72, 4.82)])}>NaN contributions in the last year</text>'
    head += f'<text x="0" y="17" font-size="16" fill="{c["danger"]}" {A.windows([(5.0, 5.06)])}>-1 contributions in the last year</text>'
    for color, sign in (("#ff0055", 1), ("#00e5ff", -1)):
        fr = [(0, "opacity:0")]
        for k, tt in enumerate([4.4, 4.5, 4.6, 4.7, 4.8, 4.9]):
            fr.append((tt, f"opacity:.75;transform:translate({sign * rnd.uniform(2, 5):.1f}px,{rnd.uniform(-1, 1):.1f}px)"))
        fr += [(5.0, "opacity:0"), (T, "opacity:0")]
        head += f'<text x="0" y="17" font-size="16" fill="{color}" {A.add(fr, steps=True)}>{big}</text>'
    o(head + "</g>")

    # Box outline drops last, heavy and slow.
    o(f'<rect class="fx" x=".5" y="{BOX_Y + .5}" width="{W - 1}" height="{BOX_H}" rx="6" '
      f'stroke="{c["border"]}" {A.fall(7.0, rnd, heavy=True)}/>')

    # Month labels at the first column of each month (GitHub skips cramped ones).
    last_col = -9
    for col in range(ncols):
        firsts = [d for d in days if d[0] == col and d[2].day == 1]
        if firsts and col - last_col >= 2:
            o(f'<text class="fx" x="{GRID_X + col * PITCH}" y="62" font-size="12" fill="{c["fg"]}" '
              f'{A.fall(rnd.uniform(6.0, 6.8), rnd)}>{firsts[0][2].strftime("%b")}</text>')
            last_col = col
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        o(f'<text class="fx" x="36" y="{GRID_Y + row * PITCH + 9}" font-size="12" fill="{c["fg"]}" '
          f'{A.fall(rnd.uniform(6.2, 6.9), rnd)}>{name}</text>')

    # Footer.
    fy = BOX_Y + BOX_H - 13
    o(f'<text class="fx" x="41" y="{fy}" font-size="12" fill="{c["muted"]}" '
      f'{A.fall(6.5, rnd)}>Learn how we count contributions</text>')
    o(f'<text class="fx" x="855" y="{fy}" font-size="12" fill="{c["muted"]}" text-anchor="end" '
      f'{A.fall(6.6, rnd)}>More</text>')
    for i in range(5):
        x = 823 - CELL - 14 * (4 - i)
        o(f'<rect class="fx" x="{x}" y="{fy - 10}" width="{CELL}" height="{CELL}" rx="2" fill="{c["cells"][i]}" '
          f'stroke="{c["cell_border"]}" {A.fall(6.3 + i * .08, rnd)}/>')
    o(f'<text class="fx" x="{823 - CELL - 14 * 4 - 4}" y="{fy}" font-size="12" fill="{c["muted"]}" '
      f'text-anchor="end" {A.fall(6.7, rnd)}>Less</text>')

    # Cells: green takeover sweep, red corruption, then collapse from an epicentre.
    ex, ey = 38, 3
    for col, row, _, lvl in days:
        x, y = GRID_X + col * PITCH, GRID_Y + row * PITCH
        dist = math.hypot(col - ex, (row - ey) * 1.6)
        start = 5.1 + dist * .026 + rnd.uniform(0, .25)
        sweep = 3.5 + col * .016
        green = c["cells"][rnd.choice([2, 3, 3, 4, 4, 4])]
        cell = (f'<g transform="translate({x},{y})"><g class="fx" {A.fall(start, rnd)}>'
                f'<rect width="{CELL}" height="{CELL}" rx="2" fill="{c["cells"][lvl]}" stroke="{c["cell_border"]}" stroke-width=".5"/>'
                f'<rect width="{CELL}" height="{CELL}" rx="2" fill="{green}" opacity="0" '
                f'{A.windows([(sweep, 15.6)])}/>')
        if rnd.random() < .13:
            wins, a = [], rnd.uniform(4.15, 4.4)
            while a < min(start, 5.4):
                b = a + rnd.uniform(.04, .12)
                wins.append((a, b))
                a = b + rnd.uniform(.05, .25)
            if wins:
                cell += (f'<rect width="{CELL}" height="{CELL}" rx="2" fill="{rnd.choice(["#ff1e3c", "#ff0055", "#b388ff"])}" '
                         f'opacity="0" {A.windows(wins)}/>')
        o(cell + "</g></g>")
    o("</g>")

    # Glitch bars.
    for _ in range(14):
        wins, a = [], rnd.uniform(4.25, 4.9)
        for _ in range(rnd.randint(1, 3)):
            b = a + rnd.uniform(.03, .09)
            wins.append((a, b))
            a = b + rnd.uniform(.04, .2)
        if rnd.random() < .4:
            a = rnd.uniform(8.3, 9.3)
            wins.append((a, a + rnd.uniform(.03, .07)))
        wins.sort()
        o(f'<rect x="{rnd.uniform(0, W * .6):.0f}" y="{rnd.uniform(0, H):.0f}" width="{rnd.uniform(80, 450):.0f}" '
          f'height="{rnd.uniform(2, 9):.0f}" fill="{rnd.choice(["#ff0055", "#00e5ff", c["cells"][4], "#ffffff"])}" '
          f'opacity="0" {A.windows(wins, on=".85")}/>')

    # ---------- GitHub-style error flash ----------
    bx, by, bw, bh = 78, 72, 740, 76
    shake = [(0, "opacity:0;transform:translate(0,-10px)"), (7.3, "opacity:0;transform:translate(0,-10px)"),
             (7.5, "opacity:1;transform:translate(0,0)"), (8.3, "opacity:1;transform:translate(0,0)")]
    for k, dx in enumerate([-7, 6, -4, 3, 0]):
        shake.append((8.34 + k * .04, f"opacity:1;transform:translate({dx}px,0)"))
    shake += [(9.35, "opacity:1;transform:translate(0,0)"), (9.4, "opacity:0"), (T, "opacity:0")]
    zalgo = "S̷o̸m̴e̷t̶h̷i̵n̶g̵ ̶i̴s̸ ̶w̶a̴t̶c̸h̶i̵n̶g̶ ̷y̶o̸u̵."
    o(f'<g opacity="0" {A.add(shake)}>'
      f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6" fill="{c["flash_bg"]}" stroke="{c["flash_border"]}"/>'
      f'<path transform="translate({bx + 18},{by + 17})" fill="{c["danger"]}" d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 '
      f'11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 '
      f'.22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z"/>'
      f'<text x="{bx + 46}" y="{by + 29}" font-size="14" font-weight="600" fill="{c["fg"]}" {A.windows([(0, 8.34), (15.6, T)])}>Something went wrong.</text>'
      f'<text x="{bx + 46}" y="{by + 29}" font-size="14" font-weight="600" fill="{c["danger"]}" {A.windows([(8.34, 9.4)])}>{zalgo}</text>'
      f'<text x="{bx + 46}" y="{by + 53}" font-size="12" font-family="{MONO}" fill="{c["muted"]}">'
      f'TypeError: Cannot read properties of undefined (reading \'contributions\')</text></g>')

    # ---------- CRT power-off ----------
    o(f'<rect width="{W}" height="{H}" rx="6" fill="#07070b" opacity="0" '
      f'{A.add([(0, "opacity:0"), (9.44, "opacity:0"), (9.45, "opacity:1"), (15.2, "opacity:1"), (15.55, "opacity:0"), (T, "opacity:0")])}/>')
    crt = A.add([(0, "opacity:0"), (9.39, "opacity:0;transform:scale(1,1)"),
                 (9.4, "opacity:.95;transform:scale(1,1)", "cubic-bezier(.7,0,1,1)"),
                 (9.56, "opacity:1;transform:scale(1,.008)", "cubic-bezier(.5,0,.9,.5)"),
                 (9.76, "opacity:1;transform:scale(0,.008)"), (9.8, "opacity:0;transform:scale(0,.008)"), (T, "opacity:0")])
    o(f'<rect class="fx" width="{W}" height="{H}" fill="#fff" opacity="0" {crt}/>')

    # ---------- hidden scene ----------
    RED = "#ff1e3c"
    fin = [(0, "opacity:0;transform:scale(1,.01)"), (10.0, "opacity:0;transform:scale(1,.01)", "cubic-bezier(.2,.9,.3,1)"),
           (10.02, "opacity:1;transform:scale(1,.01)", "cubic-bezier(.2,.9,.3,1)"), (10.2, "opacity:1;transform:scale(1,1)"),
           (15.2, "opacity:1;transform:scale(1,1)"), (15.55, "opacity:0;transform:scale(1,1)"), (T, "opacity:0")]
    o(f'<g class="fx" opacity="0" {A.add(fin)}>')
    o(f'<rect width="{W}" height="{H}" rx="6" fill="#07070b"/>')
    o(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="6" stroke="{RED}" stroke-opacity=".25"/>')
    o(f'<text x="18" y="196" font-size="128" font-weight="900" font-family="{JP}" fill="{RED}" opacity=".07">ようこそ</text>')

    # Blood moon.
    mx, my, mr = 738, 110, 76
    rise = A.add([(0, "opacity:0;transform:translate(0,40px)"), (10.2, "opacity:0;transform:translate(0,40px)", "cubic-bezier(.2,.8,.2,1)"),
                  (11.4, "opacity:1;transform:translate(0,0)"), (T, "opacity:1;transform:translate(0,0)")])
    o(f'<g {rise}><circle cx="{mx}" cy="{my}" r="{mr + 6}" fill="{RED}" opacity=".45" filter="url(#glow)"/>'
      f'<circle cx="{mx}" cy="{my}" r="{mr}" fill="url(#moon)"/>')
    for k, (off, h) in enumerate([(10, 1.5), (24, 2.5), (36, 3.5), (47, 4.5), (57, 5.5), (66, 7)]):
        o(f'<rect x="{mx - mr - 8}" y="{my + off}" width="{2 * mr + 16}" height="{h}" fill="#07070b"/>')
    o("</g>")
    for i, ch in enumerate("システム侵入"):
        o(f'<text x="{W - 16}" y="{34 + i * 17}" font-size="12" font-family="{JP}" fill="{RED}" opacity=".75" text-anchor="middle">{ch}</text>')

    # Typed prompt.
    o(f'<text x="48" y="54" font-size="13" font-family="{MONO}" fill="{RED}" letter-spacing="1">&gt; ACCESS GRANTED'
      f'<tspan class="blink">_</tspan></text>')
    typing = [(0, "transform:translate(0,0)")]
    for k in range(18):
        typing.append((10.35 + k * .045, f"transform:translate({k * 8.4:.1f}px,0)"))
    typing.append((T, "transform:translate(0,0)"))
    o(f'<rect x="46" y="40" width="190" height="20" fill="#07070b" {A.add(typing, steps=True)}/>')

    # Name with chromatic aberration and slice glitches.
    name = escape(LOGIN.upper())
    bursts = [(10.05, 10.55, 9), (12.1, 12.3, 5), (14.0, 14.25, 6)]

    def aberr(sign, amp):
        fr = [(0, "transform:translate(0,0)")]
        for a, b, _ in bursts:
            tt = a
            while tt < b:
                fr.append((tt, f"transform:translate({sign * rnd.uniform(1, amp):.1f}px,{rnd.uniform(-1.5, 1.5):.1f}px)"))
                tt += .05
            fr.append((b, "transform:translate(0,0)"))
        fr.append((T, "transform:translate(0,0)"))
        return A.add(fr, steps=True)

    flick = A.windows([(10.05, 10.1), (10.18, 10.22), (10.3, T)])
    o(f'<g {flick}>')
    o(f'<use href="#nm" fill="{RED}" {aberr(1, 9)}/>')
    o(f'<use href="#nm" fill="#00e5ff" {aberr(-1, 9)}/>')
    o(f'<use href="#nm" fill="#f5f5f7"/>')
    for k, (y0, h) in enumerate([(78, 9), (96, 6), (106, 8)]):
        o(f'<g clip-path="url(#sl{k})"><rect x="40" y="{y0}" width="560" height="{h}" fill="#07070b" {aberr(1, 1)}/>'
          f'<use href="#nm" fill="#f5f5f7" {aberr(rnd.choice([-1, 1]), 22)}/></g>')
    o("</g>")

    o(f'<text x="48" y="146" font-size="13" font-family="{MONO}" fill="#8b8b99">you weren\'t supposed to see the real graph.</text>')
    o(f'<text x="48" y="166" font-size="13" font-family="{MONO}" fill="#8b8b99">it\'s somewhere below. <tspan fill="{RED}">probably.</tspan></text>')
    for k in range(5):
        o(f'<text x="48" y="198" font-size="11" font-family="{MONO}" fill="#55556a" {A.windows([(10.4 + k, 11.4 + k if k < 4 else 15.2)])}>'
          f'[0x539] restoring normal profile in {5 - k}…</text>')

    # CRT texture.
    o(f'<rect width="{W}" height="{H}" rx="6" fill="url(#scan)"/>')
    o(f'<rect class="roll" x="0" y="-60" width="{W}" height="60" fill="url(#band)"/>')
    o("</g>")

    defs = (f'<defs><radialGradient id="moon" cx=".38" cy=".35" r=".75"><stop offset="0" stop-color="#ff7a86"/>'
            f'<stop offset=".45" stop-color="#e0142f"/><stop offset="1" stop-color="#4a0010"/></radialGradient>'
            f'<filter id="glow" x="-1" y="-1" width="3" height="3"><feGaussianBlur stdDeviation="18"/></filter>'
            f'<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".45"/></pattern>'
            f'<linearGradient id="band" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="#fff" stop-opacity=".05"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
            f'<text id="nm" x="46" y="118" font-size="58" font-weight="800" letter-spacing="3">{name}</text>'
            + "".join(f'<clipPath id="sl{k}"><rect x="0" y="{y0}" width="{W}" height="{h}"/></clipPath>'
                      for k, (y0, h) in enumerate([(78, 9), (96, 6), (106, 8)]))
            + "</defs>")
    css = ("<style>.fx{transform-box:fill-box;transform-origin:center}"
           ".blink{animation:bl 1s steps(1,end) infinite}@keyframes bl{50%%{fill-opacity:0}}"
           ".roll{animation:rl 3.2s linear infinite}@keyframes rl{to{transform:translate(0,%dpx)}}%s</style>"
           % (H + 60, "".join(A.css)))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none" font-family="{FONT}">'
            f'{css}{defs}{"".join(out)}</svg>')


def main():
    total, days = fetch()
    os.makedirs("assets", exist_ok=True)
    for theme in THEMES:
        path = f"assets/glitch-{theme}.svg"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(build(theme, total, days))
        print(f"{path}: {os.path.getsize(path) // 1024} KB, {total} contributions")


if __name__ == "__main__":
    main()
