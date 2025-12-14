# Generated manually to fix split-brain legacy images
# Migration 0236 only handled recipes with ZERO RecipeImage entries.
# This migration handles recipes that have BOTH a legacy image AND gallery items.
#
# Runtime: O(n) where n = recipes with legacy image field populated.
#          Typically fast (<1s) for most deployments. Large instances (>10k recipes)
#          may take a few seconds. Safe to run multiple times (idempotent).
#
# Safety: Read-heavy, only writes when legacy image missing from gallery.
#         No data is deleted. Reverse migration is a no-op.
#         Wrapped in atomic transaction for consistency.
from django.db import migrations, transaction


def migrate_split_brain_images(apps, schema_editor):
    """
    Find recipes where the legacy 'image' field has a value but that image
    is NOT already in the RecipeImage gallery. Add the legacy image to the gallery.

    Idempotent: Checks for existing gallery entry before creating, so safe to re-run.
    Uses atomic transaction to ensure data consistency.
    """
    Recipe = apps.get_model('cookbook', 'Recipe')
    RecipeImage = apps.get_model('cookbook', 'RecipeImage')

    # Get all recipes with a legacy image field populated
    recipes_with_legacy = Recipe.objects.exclude(image='').exclude(image__isnull=True)

    migrated_count = 0
    skipped_count = 0

    with transaction.atomic():
        for recipe in recipes_with_legacy:
            # Check if this exact legacy image path already exists in the gallery
            legacy_image_str = str(recipe.image) if recipe.image else ''
            if not legacy_image_str:
                continue

            # Idempotency guard: skip if legacy image already exists in gallery
            legacy_exists = RecipeImage.objects.filter(
                recipe=recipe,
                image=recipe.image
            ).exists()

            if legacy_exists:
                skipped_count += 1
                continue

            # Check if there's already a primary image
            has_primary = RecipeImage.objects.filter(
                recipe=recipe,
                is_primary=True
            ).exists()

            # Get the next sort order
            max_order = RecipeImage.objects.filter(recipe=recipe).count()

            # Create the RecipeImage entry for the legacy image
            RecipeImage.objects.create(
                recipe=recipe,
                image=recipe.image,
                is_primary=not has_primary,  # Only set as primary if none exists
                sort_order=0 if not has_primary else max_order,
                created_by=recipe.created_by
            )
            migrated_count += 1

    if migrated_count > 0 or skipped_count > 0:
        print(f"  Split-brain migration: {migrated_count} migrated, {skipped_count} already present")


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - this is a no-op since we don't want to delete images.
    The legacy 'image' field still exists, so no data is lost.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cookbook', '0237_recipeimage_unique_primary_constraint'),
    ]

    operations = [
        migrations.RunPython(migrate_split_brain_images, reverse_migration),
    ]
