# -*- coding: utf-8 -*-
"""TextLens 桌面启动器。
仅用作入口：以无控制台方式拉起项目主程序 main.py。
打包成单文件 exe 后可带猫爪图标放在桌面，双击即启动。
"""
import os
import subprocess
import sys

# 启动器 exe 通常放在桌面，项目文件夹就在它同级目录的 TextLens 下
EXE_DIR = os.path.dirname(os.path.abspath(sys.executable))
PROJECT = os.path.join(EXE_DIR, "TextLens")
PYTHONW = r"C:\Users\46296\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe"
MAIN = os.path.join(PROJECT, "main.py")


def main():
    if not os.path.exists(MAIN):
        return
    subprocess.Popen([PYTHONW, MAIN], cwd=PROJECT)


if __name__ == "__main__":
    main()
