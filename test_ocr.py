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

async def run():
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(png)
    await writer.store_async()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    result = await engine.recognize_async(bitmap)
    print("OCR result:", repr(result.text))

asyncio.run(run())
