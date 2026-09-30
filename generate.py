#!/usr/bin/env python3
"""Builds assets/glitch-{dark,light}.svg: the profile's contribution graph,
drawn from live GitHub data in GitHub's exact style. It glitches, collapses,
and its own squares reassemble into the owner's name before snapping back.
Pure CSS animation, no JS, so it survives GitHub's image proxy.

Usage: python generate.py [login]   (token: $GH_TOKEN, $GITHUB_TOKEN or `gh auth token`)
"""
import json
import math
import os
import random
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timezone

LOGIN = os.environ.get("LOGIN") or (sys.argv[1] if len(sys.argv) > 1 else "VYefimenko")
T = 16.0          # full cycle, seconds
W, H = 896, 220   # native width of the profile main column
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
JP = "'Yu Gothic','Hiragino Sans','Noto Sans JP','Noto Sans CJK JP',Meiryo,sans-serif"
RED, CYAN, NIGHT, WHITE = "#ff1e3c", "#00e5ff", "#07070b", "#f5f5f7"

# Exact values from GitHub's primer CSS.
THEMES = {
    "dark": dict(fg="#f0f6fc", muted="#9198a1", border="#3d444d", cell_border="#0104090d",
                 cells=["#151b23", "#033a16", "#196c2e", "#2ea043", "#56d364"], danger="#f85149"),
    "light": dict(fg="#1f2328", muted="#59636e", border="#d1d9e0", cell_border="#1f23280d",
                  cells=["#eff2f5", "#aceebb", "#4ac26b", "#2da44e", "#116329"], danger="#d1242f"),
}
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

# Geometry measured from the live profile page.
GRID_X, GRID_Y, PITCH, CELL = 69, 73, 15, 11
BOX_Y, BOX_H = 32, 179

# 5x7 pixel font for the name the squares assemble into.
GLYPHS = {
    "A": ".111.|1...1|1...1|11111|1...1|1...1|1...1", "B": "1111.|1...1|1...1|1111.|1...1|1...1|1111.",
    "C": ".1111|1....|1....|1....|1....|1....|.1111", "D": "1111.|1...1|1...1|1...1|1...1|1...1|1111.",
    "E": "11111|1....|1....|1111.|1....|1....|11111", "F": "11111|1....|1....|1111.|1....|1....|1....",
    "G": ".1111|1....|1....|1.111|1...1|1...1|.111.", "H": "1...1|1...1|1...1|11111|1...1|1...1|1...1",
    "I": ".111.|..1..|..1..|..1..|..1..|..1..|.111.", "J": "..111|...1.|...1.|...1.|...1.|1..1.|.11..",
    "K": "1...1|1..1.|1.1..|11...|1.1..|1..1.|1...1", "L": "1....|1....|1....|1....|1....|1....|11111",
    "M": "1...1|11.11|1.1.1|1.1.1|1...1|1...1|1...1", "N": "1...1|11..1|1.1.1|1..11|1...1|1...1|1...1",
    "O": ".111.|1...1|1...1|1...1|1...1|1...1|.111.", "P": "1111.|1...1|1...1|1111.|1....|1....|1....",
    "R": "1111.|1...1|1...1|1111.|1.1..|1..1.|1...1", "S": ".1111|1....|1....|.111.|....1|....1|1111.",
    "T": "11111|..1..|..1..|..1..|..1..|..1..|..1..", "U": "1...1|1...1|1...1|1...1|1...1|1...1|.111.",
    "V": "1...1|1...1|1...1|1...1|1...1|.1.1.|..1..", "W": "1...1|1...1|1...1|1.1.1|1.1.1|11.11|1...1",
    "X": "1...1|1...1|.1.1.|..1..|.1.1.|1...1|1...1", "Y": "1...1|1...1|.1.1.|..1..|..1..|..1..|..1..",
    "Z": "11111|....1|...1.|..1..|.1...|1....|11111",
}
NAME_PITCH, NAME_Y = 13, 46


def token():
    t = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    return t or subprocess.check_output(["gh", "auth", "token"], text=True).strip()


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


def name_pixels(text):
    """Top-left corners (x, y) of the pixels of `text` in the 5x7 font, centred horizontally."""
    cols = len(text) * 6 - 1
    x0 = (W - (cols * NAME_PITCH - (NAME_PITCH - CELL))) / 2
    px = []
    for i, ch in enumerate(text):
        for r, line in enumerate(GLYPHS[ch].split("|")):
            for cidx, bit in enumerate(line):
                if bit == "1":
                    px.append((x0 + (i * 6 + cidx) * NAME_PITCH, NAME_Y + r * NAME_PITCH))
    return px


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

    def fly(self, start, dx, dy, rnd):
        """Hop, swoop to (dx, dy) and hold there, then rewind at loop end."""
        home = "transform:translate(0,0) rotate(0)"
        spin = rnd.choice([-1, 1]) * rnd.uniform(90, 200)
        mid = f"transform:translate({dx * .55:.1f}px,{dy * .55 - 25:.1f}px) rotate({spin:.0f}deg)"
        there = f"transform:translate({dx:.1f}px,{dy:.1f}px) rotate(0)"
        return self.add([
            (0, home), (start, home, "cubic-bezier(.3,0,.6,1)"),
            (start + .12, "transform:translate(0,-6px) rotate(0)", "cubic-bezier(.4,0,.6,1)"),
            (start + .55, mid, "cubic-bezier(.2,.8,.3,1)"), (start + .95, there),
            (15.35, there, "cubic-bezier(.6,0,.2,1)"), (T, home)])


def fmt(n):
    return f"{n:,} contribution{'s' if n != 1 else ''} in the last year"


def build(theme, total, days, synced):
    c = THEMES[theme]
    rnd = random.Random(1337)
    A = Anim()
    out = []
    o = out.append

    # ---------- name targets & which squares fly there ----------
    targets = sorted(name_pixels(LOGIN.upper()))
    cells = sorted(days, key=lambda d: (d[0], d[1]))
    step = (len(cells) - 1) / (len(targets) - 1)
    flyers = {id(cells[round(k * step)]): targets[k] for k in range(len(targets))}
    bursts = [(8.05, 8.45, 8), (10.9, 11.1, 5), (13.2, 13.45, 6)]
    scene = A.add([(0, "opacity:0"), (8.04, "opacity:0"), (8.05, "opacity:1"), (15.2, "opacity:1"),
                   (15.5, "opacity:0"), (T, "opacity:0")])

    # ---------- backdrop of the hidden scene (under the squares) ----------
    o(f'<g opacity="0" {scene}>')
    o(f'<rect width="{W}" height="{H}" rx="6" fill="{NIGHT}"/>')
    o(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="6" stroke="{RED}" stroke-opacity=".25"/>')
    mx, my, mr = W / 2, 92, 90
    rise = A.add([(0, "opacity:0;transform:translate(0,50px)"), (8.2, "opacity:0;transform:translate(0,50px)",
                   "cubic-bezier(.2,.8,.2,1)"), (9.6, "opacity:1;transform:translate(0,0)"), (T, "opacity:1;transform:translate(0,0)")])
    o(f'<g {rise}><circle cx="{mx}" cy="{my}" r="{mr + 8}" fill="{RED}" opacity=".4" filter="url(#glow)"/>'
      f'<circle cx="{mx}" cy="{my}" r="{mr}" fill="url(#moon)"/>')
    for off, h in [(12, 1.5), (27, 2.5), (40, 3.5), (52, 4.5), (63, 5.5), (73, 7), (82, 9)]:
        o(f'<rect x="{mx - mr - 10}" y="{my + off}" width="{2 * mr + 20}" height="{h}" fill="{NIGHT}"/>')
    o("</g>")
    for x, word in ((16, "システム侵入"), (W - 16, "信号回復")):
        for i, ch in enumerate(word):
            o(f'<text x="{x}" y="{40 + i * 17}" font-size="12" font-family="{JP}" fill="{RED}" opacity=".7" text-anchor="middle">{ch}</text>')
    o('<g filter="url(#glow2)" opacity=".85">' + "".join(
        f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="{RED}"/>' for x, y in targets) + "</g>")
    for color, sign in ((RED, 1), (CYAN, -1)):
        fr = [(0, "opacity:0")]
        for a, b, amp in bursts:
            tt = a
            while tt < b:
                fr.append((tt, f"opacity:1;transform:translate({sign * rnd.uniform(2, amp):.1f}px,{rnd.uniform(-2, 2):.1f}px)"))
                tt += .05
            fr.append((b, "opacity:0"))
        fr.append((T, "opacity:0"))
        o(f'<g opacity="0" {A.add(fr, steps=True)}>' + "".join(
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{color}"/>' for x, y in targets) + "</g>")

    o(f'<text x="36" y="26" font-size="12" font-family="{MONO}" fill="{RED}" letter-spacing="1">&gt; SIGNAL RECOVERED'
      f'<tspan class="blink">_</tspan></text>')
    typing = [(0, "transform:translate(0,0)")]
    for k in range(19):
        typing.append((8.4 + k * .04, f"transform:translate({k * 7.8:.1f}px,0)"))
    typing.append((T, "transform:translate(0,0)"))
    o(f'<rect x="34" y="12" width="180" height="20" fill="{NIGHT}" {A.add(typing, steps=True)}/>')
    fade1 = A.add([(0, "opacity:0"), (9.0, "opacity:0"), (9.5, "opacity:1"), (T, "opacity:1")])
    fade2 = A.add([(0, "opacity:0"), (9.6, "opacity:0"), (10.1, "opacity:1"), (T, "opacity:1")])
    o(f'<text x="36" y="170" font-size="13" font-family="{MONO}" fill="#8b8b99" {fade1}>every square here is a real commit.</text>')
    o(f'<text x="36" y="189" font-size="13" font-family="{MONO}" fill="#8b8b99" {fade2}>they just don\'t like being '
      f'<tspan fill="{RED}">watched.</tspan></text>')
    for k in range(5):
        o(f'<text x="36" y="209" font-size="11" font-family="{MONO}" fill="#55556a" '
          f'{A.windows([(10.2 + k, 11.2 + k if k < 4 else 15.2)])}>[0x539] reassembling in {5 - k}…</text>')
    o(f'<text x="{W - 36}" y="209" font-size="11" font-family="{MONO}" fill="#55556a" text-anchor="end" {fade2}>'
      f'{total:,} real contributions · synced {synced}</text>')
    o("</g>")

    # ---------- the graph ----------
    jitter = [(0, "transform:translate(0,0)"), (3.3, "transform:translate(-4px,0)"),
              (3.36, "transform:translate(2px,0)"), (3.42, "transform:translate(0,0)")]
    t = 4.4
    while t < 5.0:
        jitter.append((t, f"transform:translate({rnd.uniform(-6, 6):.1f}px,{rnd.uniform(-2, 2):.1f}px) "
                          f"skewX({rnd.uniform(-4, 4):.1f}deg)"))
        t += .05
    jitter += [(5.0, "transform:translate(0,3px)"), (5.08, "transform:translate(0,0)")]
    for a, b, amp in bursts:
        tt = a
        while tt < b:
            jitter.append((tt, f"transform:translate({rnd.uniform(-amp, amp) * .5:.1f}px,0) skewX({rnd.uniform(-6, 6):.1f}deg)"))
            tt += .05
        jitter.append((b, "transform:translate(0,0)"))
    jitter.append((T, "transform:translate(0,0)"))
    o(f'<g {A.add(jitter, steps=True)}>')

    # Heading: real count, then it spins up to 999,999,999 with corrupt flashes.
    head = f'<g class="fx" {A.fall(6.1, rnd, heavy=True)}>'
    real = max(total, 1)
    head += f'<text x="0" y="17" font-size="16" fill="{c["fg"]}" {A.windows([(0, 3.5), (15.6, T)])}>{fmt(total)}</text>'
    for i in range(1, 10):
        v, a = int(real * (999_999_999 / real) ** (i / 10)), 3.4 + i * .1
        head += f'<text x="0" y="17" font-size="16" fill="{c["fg"]}" {A.windows([(a, a + .1)])}>{fmt(v)}</text>'
    big = fmt(999_999_999)
    head += f'<text x="0" y="17" font-size="16" fill="{c["fg"]}" {A.windows([(4.4, 4.72), (4.82, 5.0), (5.06, 15.6)])}>{big}</text>'
    head += f'<text x="0" y="17" font-size="16" fill="{c["danger"]}" {A.windows([(4.72, 4.82)])}>NaN contributions in the last year</text>'
    head += f'<text x="0" y="17" font-size="16" fill="{c["danger"]}" {A.windows([(5.0, 5.06)])}>-1 contributions in the last year</text>'
    for color, sign in (("#ff0055", 1), (CYAN, -1)):
        fr = [(0, "opacity:0")]
        for tt in (4.4, 4.5, 4.6, 4.7, 4.8, 4.9):
            fr.append((tt, f"opacity:.75;transform:translate({sign * rnd.uniform(2, 5):.1f}px,{rnd.uniform(-1, 1):.1f}px)"))
        fr += [(5.0, "opacity:0"), (T, "opacity:0")]
        head += f'<text x="0" y="17" font-size="16" fill="{color}" {A.add(fr, steps=True)}>{big}</text>'
    o(head + "</g>")

    o(f'<rect class="fx" x=".5" y="{BOX_Y + .5}" width="{W - 1}" height="{BOX_H}" rx="6" '
      f'stroke="{c["border"]}" {A.fall(6.9, rnd, heavy=True)}/>')

    # Month labels sit over the week that contains the 1st.
    last_col = -9
    for col in range(max(d[0] for d in days) + 1):
        firsts = [d for d in days if d[0] == col and d[2].day == 1]
        if firsts and col - last_col >= 2:
            o(f'<text class="fx" x="{GRID_X + col * PITCH}" y="62" font-size="12" fill="{c["fg"]}" '
              f'{A.fall(rnd.uniform(5.9, 6.6), rnd)}>{firsts[0][2].strftime("%b")}</text>')
            last_col = col
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        o(f'<text class="fx" x="36" y="{GRID_Y + row * PITCH + 9}" font-size="12" fill="{c["fg"]}" '
          f'{A.fall(rnd.uniform(6.0, 6.7), rnd)}>{name}</text>')

    fy = BOX_Y + BOX_H - 13
    o(f'<text class="fx" x="41" y="{fy}" font-size="12" fill="{c["muted"]}" '
      f'{A.fall(6.3, rnd)}>Learn how we count contributions</text>')
    o(f'<text class="fx" x="855" y="{fy}" font-size="12" fill="{c["muted"]}" text-anchor="end" '
      f'{A.fall(6.4, rnd)}>More</text>')
    for i in range(5):
        o(f'<rect class="fx" x="{823 - CELL - 14 * (4 - i)}" y="{fy - 10}" width="{CELL}" height="{CELL}" rx="2" '
          f'fill="{c["cells"][i]}" stroke="{c["cell_border"]}" stroke-width=".5" {A.fall(6.1 + i * .08, rnd)}/>')
    o(f'<text class="fx" x="{823 - CELL - 14 * 4 - 4}" y="{fy}" font-size="12" fill="{c["muted"]}" '
      f'text-anchor="end" {A.fall(6.5, rnd)}>Less</text>')

    # Squares: green takeover, red corruption, then most collapse while the
    # chosen ones swoop into the name.
    ex, ey = 38, 3
    order = {id(d): k for k, d in enumerate(cells)}
    for d in days:
        col, row, _, lvl = d
        x, y = GRID_X + col * PITCH, GRID_Y + row * PITCH
        key = id(d)
        green = c["cells"][rnd.choice([2, 3, 3, 4, 4, 4])]
        if key in flyers:
            tx, ty = flyers[key]
            start = 6.3 + order[key] / len(cells) * .6 + rnd.uniform(0, .1)
            motion, until = A.fly(start, tx - x, ty - y, rnd), start
        else:
            dist = math.hypot(col - ex, (row - ey) * 1.6)
            start = 5.1 + dist * .026 + rnd.uniform(0, .25)
            motion, until = A.fall(start, rnd), start
        cell = (f'<g transform="translate({x},{y})"><g class="fx" {motion}>'
                f'<rect width="{CELL}" height="{CELL}" rx="2" fill="{c["cells"][lvl]}" stroke="{c["cell_border"]}" stroke-width=".5"/>'
                f'<rect width="{CELL}" height="{CELL}" rx="2" fill="{green}" opacity="0" {A.windows([(3.5 + col * .016, 15.6)])}/>')
        if key in flyers:
            cell += f'<rect width="{CELL}" height="{CELL}" rx="2" fill="{WHITE}" opacity="0" {A.windows([(8.05, 15.3)])}/>'
        if rnd.random() < .13:
            wins, a = [], rnd.uniform(4.15, 4.4)
            while a < min(until, 5.4):
                b = a + rnd.uniform(.04, .12)
                wins.append((a, b))
                a = b + rnd.uniform(.05, .25)
            if wins:
                cell += (f'<rect width="{CELL}" height="{CELL}" rx="2" fill="{rnd.choice([RED, "#ff0055", "#b388ff"])}" '
                         f'opacity="0" {A.windows(wins)}/>')
        o(cell + "</g></g>")
    o("</g>")

    # ---------- overlays ----------
    o(f'<g opacity="0" {scene}><rect width="{W}" height="{H}" rx="6" fill="url(#scan)"/>'
      f'<rect class="roll" x="0" y="-60" width="{W}" height="60" fill="url(#band)"/></g>')
    for _ in range(16):
        wins, a = [], rnd.uniform(4.25, 4.9)
        for _ in range(rnd.randint(1, 3)):
            b = a + rnd.uniform(.03, .09)
            wins.append((a, b))
            a = b + rnd.uniform(.04, .2)
        if rnd.random() < .5:
            ba, bb, _ = rnd.choice(bursts)
            a = rnd.uniform(ba, bb - .05)
            wins.append((a, a + rnd.uniform(.03, .06)))
        wins.sort()
        o(f'<rect x="{rnd.uniform(0, W * .6):.0f}" y="{rnd.uniform(0, H):.0f}" width="{rnd.uniform(80, 450):.0f}" '
          f'height="{rnd.uniform(2, 9):.0f}" fill="{rnd.choice(["#ff0055", CYAN, c["cells"][4], "#ffffff"])}" '
          f'opacity="0" {A.windows(wins, on=".85")}/>')
    flash = A.add([(0, "opacity:0"), (8.0, "opacity:0"), (8.05, "opacity:.9", "cubic-bezier(.1,.7,.3,1)"),
                   (8.4, "opacity:0"), (T, "opacity:0")])
    o(f'<rect width="{W}" height="{H}" rx="6" fill="#fff" opacity="0" {flash}/>')

    defs = (f'<defs><radialGradient id="moon" cx=".38" cy=".35" r=".75"><stop offset="0" stop-color="#ff7a86"/>'
            f'<stop offset=".45" stop-color="#e0142f"/><stop offset="1" stop-color="#4a0010"/></radialGradient>'
            f'<filter id="glow" x="-1" y="-1" width="3" height="3"><feGaussianBlur stdDeviation="20"/></filter>'
            f'<filter id="glow2" x="-.2" y="-.5" width="1.4" height="2"><feGaussianBlur stdDeviation="6"/></filter>'
            f'<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".4"/></pattern>'
            f'<linearGradient id="band" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="#fff" stop-opacity=".05"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>')
    css = ("<style>.fx{transform-box:fill-box;transform-origin:center}"
           ".blink{animation:bl 1s steps(1,end) infinite}@keyframes bl{50%%{fill-opacity:0}}"
           ".roll{animation:rl 3.2s linear infinite}@keyframes rl{to{transform:translate(0,%dpx)}}%s</style>"
           % (H + 60, "".join(A.css)))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none" '
            f'font-family="{FONT}">{css}{defs}{"".join(out)}</svg>')


def main():
    total, days = fetch()
    synced = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    os.makedirs("assets", exist_ok=True)
    for theme in THEMES:
        path = f"assets/glitch-{theme}.svg"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(build(theme, total, days, synced))
        print(f"{path}: {os.path.getsize(path) // 1024} KB, {total} contributions")


if __name__ == "__main__":
    main()
