"""
sp_add_methodology_nav.py
=========================
SOP V3.0 STEP 8 · 后处理脚本 7/7
功能：注入方法论入口（"📘 评分方法论"浮窗 + 顶栏按钮 + 详细模态框）
输入：output/*.html
输出：原地修改 output/*.html
"""
from __future__ import annotations
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sp_common as sp   # noqa: E402

ROOT = os.path.dirname(HERE)

METHODOLOGY_HTML = """
<button class="sp-meth-fab" onclick="document.getElementById('sp-meth-modal').classList.add('is-open')" aria-label="open methodology">
  📘 方法论
</button>
<div id="sp-meth-modal" class="sp-meth-modal" role="dialog" aria-modal="true" onclick="if(event.target===this)this.classList.remove('is-open')">
  <div class="sp-meth-panel">
    <button class="sp-meth-close" onclick="document.getElementById('sp-meth-modal').classList.remove('is-open')">×</button>
    <h2>SOP V3.0 评分方法论 / Methodology</h2>
    <p class="sp-muted">V3.0 缝合版：硬阈值 6 维评分 + 1 张评分矩阵总表 + 1 张否决速查表。所有 Skill 仅佐证/触发，不参与计分。</p>

    <h3>1. 方向判定 / Direction</h3>
    <table class="sp-table">
      <thead><tr><th>供需比中位数</th><th>判定</th><th>策略</th></tr></thead><tbody>
      <tr><td>&gt; 10</td><td><b>D1 需求驱动</b></td><td>蓝海/供不应求，先冲进去</td></tr>
      <tr><td>3 ~ 10</td><td><b>D2 红海差异化</b></td><td>供需均衡，拼供应链和微创新</td></tr>
      <tr><td>&lt; 3</td><td><b>D3 垂直细分</b></td><td>极度内卷，必须深耕细作</td></tr>
      </tbody></table>

    <h3>2. 六维权重 / 6-Dimension Weights</h3>
    <table class="sp-table">
      <thead><tr><th>维度</th><th>考核点</th><th>D1</th><th>D2</th><th>D3</th></tr></thead><tbody>
      <tr><td>1 市场需求</td><td>GMV / 销量波动</td><td>25%</td><td>5%</td><td>10%</td></tr>
      <tr><td>2 分散度</td><td>CR10</td><td>20%</td><td>15%</td><td>30%</td></tr>
      <tr><td>3 定价空间</td><td>毛利率</td><td>15%</td><td>25%</td><td>15%</td></tr>
      <tr><td>4 新品机会</td><td>New Release / 头部硬伤</td><td>15%</td><td>25%</td><td>20%</td></tr>
      <tr><td>5 需求强度</td><td>同比/环比 / 评论增速</td><td>25%</td><td>10%</td><td>25%</td></tr>
      <tr><td>6 品牌与合规</td><td>认证 / 专利</td><td>一票否决</td><td>20%</td><td>一票否决</td></tr>
      </tbody></table>

    <h3>3. 否决速查 / Veto Rules</h3>
    <table class="sp-table">
      <thead><tr><th>条件</th><th>D1</th><th>D2</th><th>D3</th></tr></thead><tbody>
      <tr><td>D6 = 0</td><td>T3</td><td>T3</td><td>T3</td></tr>
      <tr><td>D6 = 1~2</td><td>-10 分</td><td>正常</td><td>-10 分</td></tr>
      <tr><td>D1 = 1</td><td>T3</td><td>T3</td><td>D5=5 破格保 T2</td></tr>
      <tr><td>D2 = 1</td><td>T3</td><td>T3</td><td>T3</td></tr>
      <tr><td>D3 = 1~2</td><td>正常</td><td>T3</td><td>正常</td></tr>
      </tbody></table>

    <h3>4. 三档判定 / Tier Thresholds</h3>
    <table class="sp-table">
      <thead><tr><th>档位</th><th>D1</th><th>D2</th><th>D3</th></tr></thead><tbody>
      <tr><td>T1 必做</td><td>≥ 80</td><td>≥ 85</td><td>≥ 75</td></tr>
      <tr><td>T2 可做(复议)</td><td>60~79</td><td>70~84</td><td>55~74</td></tr>
      <tr><td>T3 放弃</td><td>&lt; 60</td><td>&lt; 70</td><td>&lt; 55</td></tr>
      </tbody></table>

    <h3>5. Skill 硬影响清单 / Skill → Score Impact</h3>
    <table class="sp-table">
      <thead><tr><th>Skill</th><th>触发场景</th><th>对评分的硬影响</th></tr></thead><tbody>
      <tr><td>Skill 11 ABA 高增长</td><td>方向边界 2.8~3.2</td><td>无直接影响</td></tr>
      <tr><td><b>Skill 25 季节前置爆破</b></td><td>STEP 6 下月增长率</td><td><b>唯一允许破格升 1 级（双条件）</b></td></tr>
      <tr><td>Skill 19 / 15 / 14</td><td>STEP 3 佐证</td><td>仅写入备注</td></tr>
      <tr><td>Skill 26 / 20</td><td>STEP 4 关键词</td><td>仅写入关键词页</td></tr>
      <tr><td>Skill 24 / 27 / 23</td><td>STEP 5 评论</td><td>仅写入评论页</td></tr>
      </tbody></table>
  </div>
</div>
"""

METHODOLOGY_CSS = """
<style>
  .sp-meth-fab{position:fixed;right:18px;bottom:18px;background:var(--cta);
    color:#0f1111;font-weight:700;border:none;border-radius:999px;padding:10px 16px;
    box-shadow:0 4px 16px rgba(0,0,0,.18);cursor:pointer;font-family:var(--font-display);
    z-index:60;font-size:13px}
  .sp-meth-fab:hover{background:#f7ca00}
  .sp-meth-modal{position:fixed;inset:0;background:rgba(15,17,17,.55);
    display:none;align-items:center;justify-content:center;z-index:80;padding:20px}
  .sp-meth-modal.is-open{display:flex}
  .sp-meth-panel{background:#fff;max-width:880px;width:100%;max-height:90vh;overflow:auto;
    border-radius:10px;padding:24px 28px;box-shadow:0 20px 60px rgba(0,0,0,.3);
    position:relative}
  .sp-meth-close{position:absolute;right:12px;top:8px;background:transparent;border:0;
    font-size:24px;cursor:pointer;color:#565959}
  .sp-meth-panel h2{margin-top:0}
  .sp-meth-panel h3{margin-top:18px;color:#0f1111}
  @media (max-width:640px){.sp-meth-fab{padding:8px 12px;font-size:12px}}
</style>
"""


def main() -> None:
    out_dir = os.path.join(ROOT, "output")
    n = 0
    for name in os.listdir(out_dir):
        if not name.endswith(".html"):
            continue
        p = os.path.join(out_dir, name)
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()
        if "sp-meth-fab" in text:
            continue
        text = text.replace("</head>", METHODOLOGY_CSS + "\n</head>", 1)
        text = text.replace("</body>", METHODOLOGY_HTML + "\n</body>", 1)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        n += 1
        print(f"[ok] methodology nav → {p}")
    print(f"[done] {n} file(s) updated")


if __name__ == "__main__":
    main()
