import uuid

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction

from core.image_styles import render_canvas_image
from core.models import Image
from osig.utils import get_osig_logger

logger = get_osig_logger(__name__)


def _get_output_extension(image_data):
    return "jpeg" if image_data.get("format") == "jpeg" else "png"


def save_generated_image(image, image_data):
    prefix = "key_" if image_data.get("key") else "no_key_"
    image_filename = f"{prefix}{uuid.uuid4().hex[:12]}.{_get_output_extension(image_data)}"

    try:
        with transaction.atomic():
            image_obj, created = Image.objects.get_or_create(image_data=image_data)

            image_content = ContentFile(image.getvalue())
            image_obj.generated_image.save(image_filename, image_content, save=True)

        action = "Saved new" if created else "Updated existing"
        return f"{action} image: {image_filename}"
    except Exception as e:
        logger.error("Error saving image", extra={"error": str(e), "image_data": image_data})
        raise


@transaction.atomic
def regenerate_and_update_image(image_id, image_data):
    try:
        image_obj = Image.objects.select_for_update().get(id=image_id)

        new_image = render_canvas_image(image_data)
        old_image_path = image_obj.generated_image.name

        if not default_storage.exists(old_image_path):
            return "Old image not found in S3, skipping regeneration"

        prefix = "key_" if image_data.get("key") else "no_key_"
        image_filename = f"{prefix}{uuid.uuid4().hex[:12]}.{_get_output_extension(image_data)}"
        image_content = ContentFile(new_image.getvalue())

        for key, value in image_data.items():
            setattr(image_obj, key, value)

        image_obj.generated_image.save(image_filename, image_content, save=True)

        if old_image_path:
            logger.info("Deleting old image", extra={"path": old_image_path})
            default_storage.delete(old_image_path)

        return "Regenerated and updated image"
    except Image.DoesNotExist:
        logger.error("Image not found for regeneration", extra={"image_id": image_id})
    except Exception as e:
        logger.error("Error regenerating image", extra={"image_id": image_id, "error": str(e)})
        raise


def add_email_to_buttondown(email, tag):
    data = {
        "email_address": str(email),
        "metadata": {"source": tag},
        "tags": [tag],
        "referrer_url": "https://osig.app",
        "type": "regular",
    }

    r = requests.post(
        "https://api.buttondown.email/v1/subscribers",
        headers={"Authorization": f"Token {settings.BUTTONDOWN_API_KEY}"},
        json=data,
    )

    return r.json()
