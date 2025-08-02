"""Background task to convert existing PNG images to WebP format."""

import asyncio
from pathlib import Path
from typing import List

from config import RESOURCES_BASE_PATH
from logger.logger import log
from PIL import Image, UnidentifiedImageError
from tasks.tasks import Task


class ConvertImagesToWebPTask(Task):
    """Task to convert existing PNG images to WebP format."""

    def __init__(self):
        super().__init__(
            title="Convert PNG images to WebP",
            description="Convert existing PNG images to WebP format for better performance",
            enabled=True,
            manual_run=True,
            cron_string=None,
        )
        self.resources_path = Path(RESOURCES_BASE_PATH)
        self.processed_count = 0
        self.error_count = 0

    def _create_webp_version(self, image_path: Path, quality: int = 85) -> bool:
        """Create a WebP version of the given image file.

        Args:
            image_path: Path to the original image file
            quality: WebP quality (0-100, default 85)

        Returns:
            True if WebP was created successfully, False otherwise
        """
        webp_path = image_path.with_suffix(".webp")

        # Skip if WebP already exists
        if webp_path.exists():
            return True

        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary (WebP doesn't support RGBA)
                if img.mode in ("RGBA", "LA", "P"):
                    # Create white background for transparent images
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(
                        img, mask=img.split()[-1] if img.mode == "RGBA" else None
                    )
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                img.save(webp_path, "WEBP", quality=quality, optimize=True)
                log.info(f"Created WebP version: {webp_path}")
                return True
        except Exception as exc:
            log.error(f"Failed to create WebP version of {image_path}: {str(exc)}")
            return False

    def _find_png_images(self) -> List[Path]:
        """Find all PNG images in the resources directory.

        Returns:
            List of paths to PNG images
        """
        png_files = []
        if self.resources_path.exists():
            png_files = list(self.resources_path.rglob("*.png"))
        return png_files

    async def run(self) -> dict:
        """Run the image conversion task.

        Returns:
            Dictionary with task results
        """
        log.info("Starting PNG to WebP conversion task")

        png_files = self._find_png_images()
        log.info(f"Found {len(png_files)} PNG files to process")

        self.processed_count = 0
        self.error_count = 0

        for png_file in png_files:
            try:
                # Verify it's a valid image file
                with Image.open(png_file) as img:
                    img.verify()

                # Create WebP version
                if self._create_webp_version(png_file):
                    self.processed_count += 1
                else:
                    self.error_count += 1

                # Yield control to prevent blocking
                if self.processed_count % 10 == 0:
                    await asyncio.sleep(0.1)

            except (UnidentifiedImageError, OSError) as exc:
                log.warning(f"Skipping invalid image file {png_file}: {str(exc)}")
                self.error_count += 1
            except Exception as exc:
                log.error(f"Unexpected error processing {png_file}: {str(exc)}")
                self.error_count += 1

        log.info(
            f"PNG to WebP conversion completed. Processed: {self.processed_count}, Errors: {self.error_count}"
        )

        return {
            "task": "convert_images_to_webp",
            "status": "completed",
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "total_files": len(png_files),
        }


# Task instance
convert_images_to_webp_task = ConvertImagesToWebPTask()
