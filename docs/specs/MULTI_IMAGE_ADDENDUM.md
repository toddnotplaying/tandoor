# Multi-Image Implementation: Addendum

**Corrections and additions to MULTI_IMAGE_IMPLEMENTATION_DETAILS.md**

---

## CORRECTION: Test File Naming

The test file should follow the existing naming convention:

**Wrong:** `cookbook/tests/api/test_recipe_images.py`
**Correct:** `cookbook/tests/api/test_api_recipe_image.py`

---

## MISSING: Task 2 - Create Migration

After creating the model in Task 1, create and apply the migration:

```bash
# Generate the migration
python manage.py makemigrations cookbook --name recipeimage

# Review the generated migration file (should be 0235 or higher)
cat cookbook/migrations/0235_recipeimage.py

# Apply the migration
python manage.py migrate cookbook

# Verify
python manage.py shell -c "from cookbook.models import RecipeImage; print(RecipeImage._meta.db_table)"
# Should output: cookbook_recipeimage
```

---

## MISSING: Task 4 - Update RecipeSerializer

Add `images` field to `RecipeSerializer` in `cookbook/serializer.py`.

### Step 1: Add the field (after line 1195)

```python
class RecipeSerializer(RecipeBaseSerializer):
    nutrition = NutritionInformationSerializer(allow_null=True, required=False)
    properties = PropertySerializer(many=True, required=False)
    steps = StepSerializer(many=True)
    keywords = KeywordSerializer(many=True, required=False)
    shared = UserSerializer(many=True, required=False)
    rating = CustomDecimalField(required=False, allow_null=True, read_only=True)
    last_cooked = serializers.DateTimeField(required=False, allow_null=True, read_only=True)
    food_properties = serializers.SerializerMethodField('get_food_properties')
    created_by = UserSerializer(read_only=True)
    images = RecipeImageSerializer(many=True, read_only=True)  # <-- ADD THIS LINE
```

### Step 2: Add to fields tuple (line 1204-1208)

```python
    class Meta:
        model = Recipe
        fields = (
            'id', 'name', 'description', 'image', 'images', 'keywords', 'steps',  # <-- ADD 'images' HERE
            'working_time', 'waiting_time', 'created_by', 'created_at', 'updated_at', 'source_url',
            'internal', 'show_ingredient_overview', 'nutrition', 'properties', 'food_properties',
            'servings', 'file_path', 'servings_text', 'rating', 'last_cooked', 'private', 'shared'
        )
        read_only_fields = ['image', 'images', 'created_by', 'created_at', 'food_properties']  # <-- ADD 'images' HERE TOO
```

### Step 3: Ensure import order

The new `RecipeImageSerializer` must be defined BEFORE `RecipeSerializer` in the file. Place it after the renamed `RecipePrimaryImageSerializer` (around line 1240).

### Verification

```bash
python manage.py shell
>>> from cookbook.serializer import RecipeSerializer
>>> print('images' in RecipeSerializer.Meta.fields)
True
```

---

## MISSING: Task 11 - Update RecipeEditor.vue

In `vue3/src/components/model_editors/RecipeEditor.vue`:

### Step 1: Add import (around line 190)

```typescript
import RecipeImageManager from "@/components/inputs/RecipeImageManager.vue"
```

### Step 2: Add component after primary image section (after line 48)

Find this section:
```vue
                            </v-img>
                        </v-col>
                    </v-row>
```

Add after it:
```vue
                    <!-- Additional images manager (only for existing recipes) -->
                    <template v-if="isUpdate() && editingObj.id">
                        <v-divider class="my-4"></v-divider>
                        <recipe-image-manager
                            v-model="editingObj.images"
                            :recipe-id="editingObj.id"
                            :disabled="loading || fileApiLoading"
                            :max-images="10"
                        />
                    </template>
```

### Step 3: Initialize images array (in initializeEditor function, around line 231)

In the `newItemFunction`, add:
```typescript
editingObj.value.images = []
```

---

## MISSING: Task 12 - Update RecipeView.vue

In `vue3/src/components/display/RecipeView.vue`:

### Step 1: Add import (in script section)

```typescript
import RecipeImageGallery from "@/components/display/RecipeImageGallery.vue"
```

### Step 2: Add gallery component (after line 118, after desktop layout)

```vue
        <!-- Image gallery for additional images -->
        <recipe-image-gallery
            v-if="recipe.images && recipe.images.length > 0"
            :images="recipe.images"
            :primary-image="recipe.image"
            class="mt-2"
        />
```

---

## MISSING: Task 13 - TypeScript Types

### Option A: Regenerate OpenAPI (Recommended)

After backend is complete:
```bash
cd vue3
npm run generate-api
```

This regenerates all types from the Django schema.

### Option B: Manual type definition

If you need types before backend is done, create `vue3/src/types/recipe-image.ts`:

```typescript
export interface RecipeImage {
    id: number
    image: string
    order: number
    createdAt?: string
    createdBy?: {
        id: number
        displayName: string
    }
}
```

Then update `vue3/src/types/index.ts`:
```typescript
export * from './recipe-image'
```

---

## MISSING: Task 14 - Add Translation Strings

Add to `vue3/src/locales/en.json`:

```json
{
    "Images": "Images",
    "Add_Image": "Add Image",
    "Maximum images reached": "Maximum images reached",
    "No additional images yet. Upload images below.": "No additional images yet. Upload images below.",
    "Uploading...": "Uploading..."
}
```

**Note:** Check if these keys already exist before adding. Some like "Images" might already be present.

---

## Task Dependency Order (Corrected)

Execute tasks in this order:

```
Backend (do first):
1. Task 1: Create Model
2. Task 2: Create Migration  <-- WAS MISSING
3. Task 3: Create Serializers
4. Task 4: Update RecipeSerializer  <-- WAS MISSING
5. Task 5: Create ViewSet
6. Task 6: Register URLs
7. Task 7: Add to Admin
8. Task 15: Write Tests

Frontend (after backend works):
9. Task 10: Add API functions to useFileApi.ts
10. Task 13: TypeScript types  <-- WAS MISSING
11. Task 14: Translation strings  <-- WAS MISSING
12. Task 8: Create RecipeImageManager.vue
13. Task 9: Create RecipeImageGallery.vue
14. Task 11: Update RecipeEditor.vue  <-- WAS MISSING
15. Task 12: Update RecipeView.vue  <-- WAS MISSING
16. Task 16: Frontend tests (optional for MVP)
```

---

## Pre-Implementation Checklist

Before starting, verify these files exist and note their current state:

```bash
# Backend files to modify
ls -la cookbook/models.py          # ~1700 lines
ls -la cookbook/serializer.py      # ~2100 lines
ls -la cookbook/views/api.py       # ~3200 lines
ls -la cookbook/urls.py
ls -la cookbook/admin.py

# Frontend files to modify
ls -la vue3/src/composables/useFileApi.ts
ls -la vue3/src/components/model_editors/RecipeEditor.vue
ls -la vue3/src/components/display/RecipeView.vue
ls -la vue3/src/locales/en.json

# Frontend files to create
ls -la vue3/src/components/inputs/          # RecipeImageManager.vue goes here
ls -la vue3/src/components/display/         # RecipeImageGallery.vue goes here

# Test file to create
ls -la cookbook/tests/api/                  # test_api_recipe_image.py goes here
```

---

## Quick Verification Commands

After each task, run these to verify:

```bash
# After Task 1 (Model)
python manage.py check

# After Task 2 (Migration)
python manage.py showmigrations cookbook | grep recipe

# After Tasks 3-6 (API)
python manage.py runserver &
curl -s http://localhost:8000/api/recipe/1/images/ | head
# Should return [] or JSON, not 404

# After Task 15 (Tests)
pytest cookbook/tests/api/test_api_recipe_image.py -v

# After frontend tasks
cd vue3 && npm run build
# Should complete without errors
```
