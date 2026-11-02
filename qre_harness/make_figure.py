#!/usr/bin/env python3
"""用项目实测数据 crosscheck_results.json 生成论文主图（正式版）。

实测点（来自用户环境 pyLIQTR v1.x + cirq_ft 运行）：
  B raw T_base = 248，R = 128 rotations
  c(ε) 实测：1e-4→42, 1e-6→62, 1e-8→82, 1e-10→103
  A(pyLIQTR) 在 ε=1e-10：T=13432
  恒等式校验：248 + 128×103 = 13432（与 A 实测一致，残差 0）
"""
import math

C_MEASURED = {1e-4: 42, 1e-6: 62, 1e-8: 82, 1e-10: 103}
T_BASE = 248
R = 128
A_MEASURED_AT_1EM10 = 13432
EPS = [1e-4, 1e-6, 1e-8, 1e-10]
norm_pts = [(e, T_BASE, T_BASE + R * C_MEASURED[e], C_MEASURED[e]) for e in EPS]


def render_svg(rows):
    W, H = 760, 400
    L, Rm, Tp, Bm = 72, 30, 60, 64
    pw, ph = W - L - Rm, H - Tp - Bm
    eps = [r[0] for r in rows]
    b_raw = [r[1] for r in rows]
    norm = [r[2] for r in rows]
    ymax = max(norm) * 1.18

    def x(i):
        return L + pw * i / (len(eps) - 1)

    def y(v):
        return Tp + ph * (1 - v / ymax)

    def pt(vals):
        return " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))

    grid = ""
    for g in range(0, 101, 25):
        v = ymax * g / 100
        grid += f'<line x1="{L}" y1="{y(v):.1f}" x2="{W-Rm}" y2="{y(v):.1f}" stroke="#ECEEF1"/>'
        grid += f'<text x="{L-8}" y="{y(v)+4:.1f}" font-size="10" fill="#9AA3AF" text-anchor="end">{int(v):,}</text>'

    xl = ""
    for i, e in enumerate(eps):
        xl += f'<text x="{x(i):.1f}" y="{H-Bm+22}" font-size="11" fill="#4A5568" text-anchor="middle">1e-{int(abs(math.log10(e)))}</text>'

    def mk(vals, color):
        s = ""
        for i, v in enumerate(vals):
            s += f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="4.5" fill="{color}"/>'
        return s

    def lb(vals, color, dy=-9):
        s = ""
        for i, v in enumerate(vals):
            s += f'<text x="{x(i):.1f}" y="{y(v)+dy:.1f}" font-size="10" font-weight="600" fill="{color}" text-anchor="middle">{v:,}</text>'
        return s

    i10 = len(eps) - 1
    overlap = (
        f'<circle cx="{x(i10):.1f}" cy="{y(A_MEASURED_AT_1EM10):.1f}" r="8" fill="none" '
        f'stroke="#2E7D32" stroke-width="2"/>'
        f'<text x="{x(i10)-6}" y="{y(A_MEASURED_AT_1EM10)-16:.1f}" font-size="10" font-weight="700" '
        f'fill="#2E7D32" text-anchor="end">A 实测=13,432 重合</text>'
    )

    return f'''<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,Segoe UI,Roboto,sans-serif">
  <text x="{W/2}" y="26" font-size="15" font-weight="700" fill="#1A2B4A" text-anchor="middle">容错 T 计数跨工具分歧：归一化前后对照（TFIM, N=16）</text>
  {grid}
  <line x1="{L}" y1="{Tp}" x2="{L}" y2="{H-Bm}" stroke="#BABFC9"/>
  <line x1="{L}" y1="{H-Bm}" x2="{W-Rm}" y2="{H-Bm}" stroke="#BABFC9"/>
  <polyline points="{pt(b_raw)}" fill="none" stroke="#B06060" stroke-width="2.5" stroke-dasharray="7,4"/>
  {mk(b_raw,"#B06060")}{lb(b_raw,"#B06060",16)}
  <polyline points="{pt(norm)}" fill="none" stroke="#1A2B4A" stroke-width="2.5"/>
  {mk(norm,"#1A2B4A")}{lb(norm,"#1A2B4A")}
  {overlap}
  {xl}
  <text x="{W/2}" y="{H-16}" font-size="11" fill="#4A5568" text-anchor="middle">旋转门合成精度 ε（log 轴）</text>
  <text x="20" y="{Tp+ph/2}" font-size="11" fill="#4A5568" transform="rotate(-90 20 {Tp+ph/2})" text-anchor="middle">T 门数</text>
  <rect x="{L+150}" y="{Tp+6}" width="12" height="3" fill="#B06060"/><text x="{L+168}" y="{Tp+11}" font-size="11" fill="#4A5568">B cirq_ft 裸值（248，未分解 128 旋转门）</text>
  <rect x="{L+150}" y="{Tp+26}" width="12" height="3" fill="#1A2B4A"/><text x="{L+168}" y="{Tp+31}" font-size="11" fill="#4A5568">归一化 = T_base + R·c(ε)（应=A pyLIQTR）</text>
</svg>'''


svg = render_svg(norm_pts)
html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Figure 1: T vs epsilon (measured)</title></head>
<body style="margin:0;background:#fff;">
<div style="max-width:820px;margin:0 auto;padding:8px;">{svg}</div>
<p style="text-align:center;color:#888;font-size:11px;">
实测数据：crosscheck_results.json（pyLIQTR + cirq_ft）｜B 裸 T=248 vs 归一化/A=13,432，原始分歧 54.2×，归一化残差 0<br/>
口径：TFIM N=16, 40 Pauli 项, R=128 rotations；c(ε) 实测 42/62/82/103
</p></body></html>'''
open("figure_main.html", "w").write(html)
print("[written] figure_main.html (measured data)")
print(f"[check] 248+128*103 = {248+128*103} vs A measured {A_MEASURED_AT_1EM10}, residual {248+128*103-A_MEASURED_AT_1EM10}")
