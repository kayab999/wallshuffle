import logging
import os

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from .utils import CONFIG_DIR, show_error_dialog


def apply_image_effect(image_path, effect_type):
    if not image_path or effect_type == "None":
        return image_path

    try:
        img = Image.open(image_path)
        if effect_type == "Grayscale":
            img = img.convert("L")
        elif effect_type == "Blur":
            img = img.filter(ImageFilter.GaussianBlur(radius=5))
        elif effect_type == "Sepia":
            # Fix Sepia implementation: convert to grayscale then colorize
            img = img.convert("L")
            img = ImageOps.colorize(img, black="#704214", white="#C0A080")

        # Ensure RGB mode for JPEG saving
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

        temp_dir = os.path.join(CONFIG_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        processed_image_path = os.path.join(temp_dir, f"processed_wallpaper_{effect_type.lower()}.jpg")
        img.save(processed_image_path)
        return processed_image_path
    except FileNotFoundError:
        logging.error(f"Image file not found for applying effect: {image_path}")
        show_error_dialog(f"Image file not found: {image_path}. Cannot apply effect.")
        return image_path
    except UnidentifiedImageError:
        logging.error(f"Cannot identify image file for applying effect: {image_path}")
        show_error_dialog(f"Cannot open or identify image file: {image_path}. It might be corrupted or an unsupported format.")
        return image_path
    except IOError as e:
        logging.error(f"File I/O error while applying image effect {effect_type} to {image_path}: {e}")
        show_error_dialog(f"Could not save processed image with {effect_type} effect. Check disk space or permissions.")
        return image_path
    except Exception as e:
        logging.critical(
            f"An unhandled error occurred in apply_image_effect for {effect_type}: {e}",
            exc_info=True,
        )
        show_error_dialog("An unexpected critical error occurred while applying image effect. Please check the logs for details.")
        return image_path
