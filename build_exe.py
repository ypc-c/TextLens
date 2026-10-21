# -*- coding: utf-8 -*-
"""把 TextLens 打包成一个独立的单文件 exe，双击即启动浮窗。

用法：
    python build_exe.py            # 增量打包，约 30~60 秒
    python build_exe.py --clean    # 清空缓存从头打包，约 1.5 分钟（首次或依赖变动时用）

产物：
    dist/TextLens.exe   （自包含，无需 Python 环境，可单独拷走）

改动 main.py 后重新执行一次本脚本即可。
"""
import os
import sys

import PyInstaller.__main__

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "assets")
SEP = os.pathsep

# 只有显式传 --clean 才清空缓存（默认增量，快很多）
CLEAN = ["--clean"] if "--clean" in sys.argv else []

ARGS = [
    "--noconfirm",
    *CLEAN,
    "--onefile",          # 全部依赖压进单个 exe
    "--windowed",         # 无控制台黑窗
    "--name=TextLens",
    f"--icon={os.path.join(ASSETS, 'app.ico')}",
    f"--add-data={os.path.join(ASSETS, 'float.png')}{SEP}assets",
    f"--add-data={os.path.join(ASSETS, 'app.ico')}{SEP}assets",
    f"--distpath={os.path.join(ROOT, 'dist')}",
    f"--workpath={os.path.join(ROOT, 'build')}",
    f"--specpath={ROOT}",
    # Windows OCR（winrt）是一组原生 .pyd，需要整体收集
    "--collect-all=winrt",
    # 与本项目无关的库，剔除后体积能小一大截
    "--exclude-module=numpy",
    "--exclude-module=tkinter",
    "--exclude-module=matplotlib",
    "--exclude-module=scipy",
    "--exclude-module=pandas",
    "--exclude-module=torch",
    "--exclude-module=IPython",
    "--exclude-module=pytest",
    os.path.join(ROOT, "main.py"),
]

def _cleanup_spec():
    """打包成功后删掉自动生成的 .spec（下次打包会重新生成，删了不影响）。"""
    spec = os.path.join(ROOT, "TextLens.spec")
    if os.path.exists(spec):
        os.remove(spec)
        print(f"已清理 {spec}", flush=True)


if __name__ == "__main__":
    # 注意：PyInstaller.__main__.run() 成功时返回 None（不是 0）
    rc = PyInstaller.__main__.run(ARGS)
    if rc in (0, None):
        _cleanup_spec()
    sys.exit(rc if isinstance(rc, int) else 0)
