"""Background task to convert existing images to WebP format."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

from PIL import Image, UnidentifiedImageError

from config import (
    ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
    RESOURCES_BASE_PATH,
    SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON,
)
from logger.logger import log
from tasks.tasks import PeriodicTask, TaskType, update_job_meta


@dataclass
class ConversionResult:
    """Result of image conversion operation."""

    success: bool
    processed_count: int
    error_count: int
    total_files: int
    errors: List[str]


class ImageConverter:
    """Handles image format conversion to WebP."""

    # Supported image formats
    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif"}

    # Image mode conversion mapping
    MODE_CONVERSIONS = {
        "P": "RGBA",  # Palette-based to RGBA (preserves transparency)
        "LA": "RGBA",  # Grayscale with alpha to RGBA
        "L": "RGB",  # Grayscale to RGB
        "CMYK": "RGB",  # CMYK to RGB
        "YCbCr": "RGB",  # YCbCr to RGB
    }

    def __init__(self, quality: int = 90):
        self.quality = quality

    def _convert_image_mode(self, img: Image.Image) -> Image.Image:
        """Convert image to appropriate mode for WebP conversion.
        Args:
            img: PIL Image object
        Returns:
            Converted PIL Image object
        """
        if img.mode in ("RGB", "RGBA"):
            return img

        target_mode = self.MODE_CONVERSIONS.get(img.mode, "RGB")
        return img.convert(target_mode)

    def convert_to_webp(self, image_path: Path, force: bool = False) -> bool:
        """Convert a single image to WebP format.
        Args:
            image_path: Path to the source image
        Returns:
            True if conversion was successful, False otherwise
        """
        webp_path = image_path.with_suffix(".webp")

        # Skip if WebP already exists
        if webp_path.exists() and not force:
            log.debug(f"WebP already exists for {image_path}")
            return True

        try:
            with Image.open(image_path) as img:
                # Convert image mode if necessary
                img = self._convert_image_mode(img)

                # Save as WebP
                img.save(webp_path, "WEBP", quality=self.quality, optimize=True)
                log.info(f"Created WebP version: {webp_path}")
                return True

        except Exception as exc:
            log.error(f"Failed to create WebP version of {image_path}: {str(exc)}")
            return False


@dataclass
class ConversionStats:
    """Statistics for cleanup operations."""

    processed: int = 0
    errors: int = 0
    total: int = 0

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        update_job_meta({"conversion_stats": self.to_dict()})

    def to_dict(self) -> dict[str, int]:
        return {
            "processed": self.processed,
            "errors": self.errors,
            "total": self.total,
        }


class ConvertImagesToWebPTask(PeriodicTask):
    """Task to convert existing images to WebP format."""

    def __init__(self):
        super().__init__(
            title="Convert images to WebP",
            description="Convert existing image files (PNG, JPG, BMP, TIFF, GIF) to WebP format for better performance",
            task_type=TaskType.CONVERSION,
            enabled=ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP,
            manual_run=True,
            cron_string=SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON,
            func="tasks.scheduled.convert_images_to_webp.convert_images_to_webp_task.run",
        )
        self.resources_path = Path(RESOURCES_BASE_PATH)
        self.converter = ImageConverter()
        self._reset_counters()

    def _reset_counters(self) -> None:
        """Reset processing counters."""
        self.processed_count = 0
        self.error_count = 0
        self.errors: list[str] = []

    def _find_convertible_images(self) -> List[Path]:
        """Find all convertible images in the resources directory.
        Returns:
            List of paths to image files that can be converted to WebP
        """
        if not self.resources_path.exists():
            log.warning(f"Resources path does not exist: {self.resources_path}")
            return []

        image_files = [
            p
            for p in self.resources_path.rglob("**/cover/*")
            if p.is_file()
            and not p.is_symlink()
            and p.suffix.lower() in ImageConverter.SUPPORTED_EXTENSIONS
            and not p.with_suffix(".webp").exists()
        ]

        return sorted(image_files)  # Sort for consistent processing order

    def _process_single_image(self, image_path: Path) -> bool:
        """Process a single image file.
        Args:
            image_path: Path to the image file
        Returns:
            True if processing was successful, False otherwise
        """
        try:
            # Validate image file first
            with Image.open(image_path) as img:
                img.verify()

            # Convert to WebP
            if self.converter.convert_to_webp(image_path):
                self.processed_count += 1
                return True
            else:
                self.error_count += 1
                self.errors.append(f"Conversion failed: {image_path}")
                return False

        except (UnidentifiedImageError, OSError) as exc:
            log.warning(f"Skipping invalid image file {image_path}: {str(exc)}")
            self.error_count += 1
            self.errors.append(f"Invalid image file: {image_path} - {str(exc)}")
            return False
        except Exception as exc:
            log.error(f"Unexpected error processing {image_path}: {str(exc)}")
            self.error_count += 1
            self.errors.append(f"Unexpected error: {image_path} - {str(exc)}")
            return False

    def _get_progress_message(self) -> str:
        """Get current progress message."""
        return f"Processed: {self.processed_count}, Errors: {self.error_count}"

    async def run(self) -> dict[str, Any]:
        """Run the image conversion task.
        Returns:
            Dictionary with task results
        """
        log.info("Starting image to WebP conversion task")

        # Find all convertible images
        conversion_stats = ConversionStats()
        image_files = self._find_convertible_images()
        total_files = len(image_files)

        if total_files == 0:
            conversion_stats.update(processed=0, errors=0, total=total_files)
            log.info("No convertible images found")
            return conversion_stats.to_dict()

        log.info(f"Found {total_files} image files to process")

        # Reset counters
        self._reset_counters()

        # Process images
        for i, image_file in enumerate(image_files, 1):
            self._process_single_image(image_file)
            conversion_stats.update(
                processed=self.processed_count,
                errors=self.error_count,
                total=total_files,
            )

            # Log progress periodically
            if i % 50 == 0 or i == total_files:
                log.info(
                    f"Progress: {i}/{total_files} - {self._get_progress_message()}"
                )

            # Yield control to prevent blocking
            if i % 10 == 0:
                await asyncio.sleep(0.1)

        # Log final results
        log.info(f"Image to WebP conversion completed. {self._get_progress_message()}")

        return conversion_stats.to_dict()


# Task instance
convert_images_to_webp_task = ConvertImagesToWebPTask()
