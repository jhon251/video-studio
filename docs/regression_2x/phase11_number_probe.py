# -*- coding: utf-8 -*-
"""Phase 11 只读探针：数字抽取精度（量词不计、计量单位计）。"""
import sys
import pathlib

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import title_check as TC                                       # noqa: E402

cases = ["机器证明最难的一步，不是算得快，而是让人相信",
         "从「99% 确定」到完全形式化，中间隔了十六年",
         "验证这一环正在被外包，数学家的活儿得重新排一遍",
         "三千页的证明没人读完", "20 年才被接受", "一页都没有", "几十万行，没一个人读完"]
for t in cases:
    print("{:34s} -> {}".format(t[:32], TC.extract_numbers(t)))
