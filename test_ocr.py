# -*- coding: utf-8 -*-
"""独立测试 Windows OCR 管线：合成中英文图片 -> OCR"""
import io, asyncio
from PIL import Image, ImageDraw, ImageFont
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.globalization import Language
from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
from winrt.windows.graphics.imaging import BitmapDecoder

engine = OcrEngine.try_create_from_user_profile_languages()
print("engine:", engine)
if engine is None:
    engine = OcrEngine.try_create_from_language(Language("zh-Hans-CN"))
    print("fallback engine:", engine)

img = Image.new("RGB", (600, 120), "white")
d = ImageDraw.Draw(img)
try:
    f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 40)
except Exception:
    f = ImageFont.load_default()
d.text((10, 30), "Hello World 你好世界 2026", font=f, fill="black")

buf = io.BytesIO()
img.save(buf, format="PNG")
png = buf.getvalue()

import re

_CJK_CLASS = r"[\u3000\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]"
_CJK_SPACE_RE = re.compile(
    r"(?<=" + _CJK_CLASS + r")[ \t\u3000]+|[ \t\u3000]+(?=" + _CJK_CLASS + r")"
)


def _clean_ocr_spaces(text):
    return _CJK_SPACE_RE.sub("", text)


async def run():
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(png)
    await writer.store_async()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    result = await engine.recognize_async(bitmap)
    print("OCR raw   :", repr(result.text))
    print("OCR cleaned:", repr(_clean_ocr_spaces(result.text or "")))

asyncio.run(run())
