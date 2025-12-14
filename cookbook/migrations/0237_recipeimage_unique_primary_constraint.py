# Generated manually for unique primary image constraint
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cookbook', '0236_migrate_legacy_images'),
    ]

    operations = [
        # First, ensure any recipes with multiple primaries are fixed
        # This is a data migration to clean up any existing violations
        migrations.RunSQL(
            sql="""
            WITH duplicates AS (
                SELECT recipe_id, MIN(id) as keep_id
                FROM cookbook_recipeimage
                WHERE is_primary = TRUE
                GROUP BY recipe_id
                HAVING COUNT(*) > 1
            )
            UPDATE cookbook_recipeimage
            SET is_primary = FALSE
            WHERE is_primary = TRUE
              AND recipe_id IN (SELECT recipe_id FROM duplicates)
              AND id NOT IN (SELECT keep_id FROM duplicates);
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Add partial unique constraint: only one is_primary=True per recipe
        migrations.AddConstraint(
            model_name='recipeimage',
            constraint=models.UniqueConstraint(
                fields=['recipe'],
                condition=models.Q(is_primary=True),
                name='unique_primary_per_recipe'
            ),
        ),
    ]
