import logging
import os

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from .constants import MAX_EFFECT_DIMENSION, ImageEffect
from .utils import CONFIG_DIR


def _maybe_downscale(image: Image.Image) -> Image.Image:
    width, height = image.size
    longest_edge = max(width, height)
    if longest_edge <= MAX_EFFECT_DIMENSION:
        return image

    scale = MAX_EFFECT_DIMENSION / longest_edge
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    logging.debug(f"Downscaling image from {width}x{height} to {new_size[0]}x{new_size[1]} before effect")
    return image.resize(new_size, Image.Resampling.LANCZOS)


def apply_image_effect(image_path, effect_type):
    if not image_path or effect_type == ImageEffect.NONE:
        return image_path

    try:
        with Image.open(image_path) as opened:
            processed: Image.Image = _maybe_downscale(opened)
            if effect_type == ImageEffect.GRAYSCALE:
                processed = processed.convert("L")
            elif effect_type == ImageEffect.BLUR:
                processed = processed.filter(ImageFilter.GaussianBlur(radius=5))
            elif effect_type == ImageEffect.SEPIA:
                gray = processed.convert("L")
                processed = ImageOps.colorize(gray, black="#704214", white="#C0A080")

            if processed.mode != "RGB":
                processed = processed.convert("RGB")

            temp_dir = os.path.join(CONFIG_DIR, "temp")
            os.makedirs(temp_dir, mode=0o700, exist_ok=True)
            processed_image_path = os.path.join(temp_dir, f"processed_wallpaper_{effect_type.lower()}.jpg")
            processed.save(processed_image_path)
            return processed_image_path
    except FileNotFoundError:
        logging.error(f"Image file not found for applying effect: {image_path}")
        return image_path
    except UnidentifiedImageError:
        logging.error(f"Cannot identify image file for applying effect: {image_path}")
        return image_path
    except OSError as error:
        logging.error(f"File I/O error while applying image effect {effect_type} to {image_path}: {error}")
        return image_path
    except Exception as error:
        logging.critical(
            f"An unhandled error occurred in apply_image_effect for {effect_type}: {error}",
            exc_info=True,
        )
        return image_path
