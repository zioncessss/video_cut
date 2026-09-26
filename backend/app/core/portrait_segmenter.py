"""
015 轻量人像分割与透明前景提取模块。
支持基于单帧视频图像进行人像前景提取、透明通道合成与羽化处理，
当缺少重型 AI 抠图模型或用户选择不抠图时提供优雅平滑降级。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple, Union

from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)


def extract_portrait_cutout(
    image_input: Union[Image.Image, Path, str],
    feather_radius: int = 4
) -> Optional[Image.Image]:
    """
    从单张图像中提取人像前景并生成 RGBA 透明图层。

    :param image_input: PIL Image 或 文件路径
    :param feather_radius: 边缘羽化半径
    :return: RGBA 透明人像图层，未检测到或降级时返回 None
    """
    try:
        if isinstance(image_input, (str, Path)):
            img = Image.open(str(image_input)).convert("RGBA")
        else:
            img = image_input.convert("RGBA")

        # 尝试使用 cv2 GrabCut 进行轻量切分（如果环境支持 cv2）
        try:
            import cv2
            import numpy as np

            rgb = np.array(img.convert("RGB"))
            h, w = rgb.shape[:2]

            # 初始中心人像经验矩形（占画面中上部约 60% 宽度，75% 高度）
            rect = (int(w * 0.15), int(h * 0.08), int(w * 0.70), int(h * 0.85))
            mask = np.zeros((h, w), np.uint8)
            bgd_model = np.zeros((1, 65), np.float64)
            fgd_model = np.zeros((1, 65), np.float64)

            cv2.grabCut(rgb, mask, rect, bgd_model, fgd_model, 2, cv2.GC_INIT_WITH_RECT)
            mask2 = np.where((mask == 2) | (mask == 0), 0, 255).astype("uint8")

            mask_img = Image.fromarray(mask2, mode="L")
            if feather_radius > 0:
                mask_img = mask_img.filter(ImageFilter.GaussianBlur(feather_radius))

            result = img.copy()
            result.putalpha(mask_img)
            return result
        except ImportError:
            logger.debug("OpenCV 未安装，轻量人像切分自动平滑降级")
            return None
        except Exception as ex:
            logger.warning("轻量人像切分运行异常，平滑降级: %s", ex)
            return None

    except Exception as e:
        logger.warning("读取输入图像失败: %s", e)
        return None
