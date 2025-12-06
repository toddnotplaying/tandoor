# Multi-Image Recipe Feature Specification

**Version:** 1.0
**Date:** 2025-12-06
**Status:** Draft
**Branch:** `claude/multi-image-recipes-012yiYmaDoSbYp7SauLrGjBB`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Goals and Non-Goals](#2-goals-and-non-goals)
3. [Technical Architecture](#3-technical-architecture)
4. [Database Schema](#4-database-schema)
5. [API Specification](#5-api-specification)
6. [Frontend Specification](#6-frontend-specification)
7. [Implementation Tasks](#7-implementation-tasks)
8. [Testing Requirements](#8-testing-requirements)
9. [Migration Strategy](#9-migration-strategy)

---

## 1. Overview

### 1.1 Current State

The Tandoor recipe management application currently supports a single image per recipe. The image is stored directly on the `Recipe` model as an `ImageField`:

```python
# cookbook/models.py:1089
image = models.ImageField(upload_to='recipes/', blank=True, null=True)
```

Images are uploaded via `PUT /api/recipe/{id}/image/` and displayed using the `RecipeImage.vue` component.

### 1.2 Proposed Change

Add support for multiple images per recipe (up to 10), allowing users to:
- Upload multiple images for a single recipe
- Reorder images via drag-and-drop
- Set a primary image (displayed as the main/cover image)
- Delete individual images

### 1.3 Scope

This specification covers the **self-hosted version only**. The following are explicitly **out of scope** for MVP:
- Multi-image support in recipe importers (URL import, AI import)
- Multi-image support in recipe export functionality
- S3/cloud storage optimizations

---

## 2. Goals and Non-Goals

### 2.1 Goals

| ID | Goal |
|----|------|
| G1 | Allow up to 10 images per recipe |
| G2 | Maintain backward compatibility with existing `Recipe.image` field |
| G3 | Provide drag-and-drop reordering of images |
| G4 | Support setting a primary/cover image |
| G5 | Follow existing codebase patterns and conventions |
| G6 | Ensure all existing functionality continues to work |

### 2.2 Non-Goals

| ID | Non-Goal |
|----|----------|
| NG1 | Multi-image support in recipe importers |
| NG2 | Multi-image support in recipe exports |
| NG3 | Image captions or alt-text (future enhancement) |
| NG4 | Image cropping or editing |
| NG5 | Cloud storage optimizations |

---

## 3. Technical Architecture

### 3.1 Technology Stack Reference

| Layer | Technology |
|-------|------------|
| Backend Framework | Django 5.2.9 |
| API Framework | Django REST Framework |
| Database | PostgreSQL (primary) |
| Frontend Framework | Vue 3 with TypeScript |
| UI Framework | Vuetify 3 |
| State Management | Pinia |
| Drag-and-Drop | vue-draggable-plus |

### 3.2 Key Files to Modify

| File | Purpose |
|------|---------|
| `cookbook/models.py` | Add RecipeImage model |
| `cookbook/serializer.py` | Add RecipeImageSerializer, update RecipeSerializer |
| `cookbook/views/api.py` | Add RecipeImageViewSet |
| `cookbook/urls.py` | Register new API routes |
| `cookbook/admin.py` | Add RecipeImage admin |
| `vue3/src/components/display/RecipeImage.vue` | Update to support multiple images |
| `vue3/src/components/display/RecipeView.vue` | Add image gallery |
| `vue3/src/components/model_editors/RecipeEditor.vue` | Multi-image upload UI |
| `vue3/src/composables/useFileApi.ts` | Add multi-image API functions |

### 3.3 Design Decision: New Model vs Alternatives

**Chosen Approach:** Create a new `RecipeImage` model with a ForeignKey to `Recipe`.

**Rationale:**
- Clean, purpose-built model for recipe images
- Follows existing patterns (similar to `Comment` model which has FK to Recipe)
- Explicit ordering via `order` field
- Easy querying: `recipe.images.all()`
- Simple migration path for existing data

**Alternatives Considered:**
- ManyToMany via UserFile: More complex, UserFile is generic
- JSONField: No referential integrity, against Django best practices
- Hybrid (keep single + add additional): Inconsistent mental model

---

## 4. Database Schema

### 4.1 New Model: RecipeImage

```python
class RecipeImage(ExportModelOperationsMixin('recipe_image'), models.Model, PermissionModelMixin):
    """
    Stores multiple images for a recipe with ordering support.
    """
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='recipes/')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE
    )

    objects = ScopedManager(space='space')

    @staticmethod
    def get_space_key():
        return 'recipe', 'space'

    def get_space(self):
        return self.recipe.space

    class Meta:
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['recipe', 'order']),
        ]
```

### 4.2 Recipe Model Changes

The existing `Recipe.image` field will be **retained** for backward compatibility. It will continue to function as before, representing the "primary" image. The new `RecipeImage` model provides additional images.

**Behavior:**
- `Recipe.image` = Primary/cover image (unchanged)
- `Recipe.images` (via related_name) = All additional images

### 4.3 Constraints

| Constraint | Value | Implementation |
|------------|-------|----------------|
| Max images per recipe | 10 | Enforced in serializer validation |
| Allowed file types | .png, .jpg, .jpeg, .gif, .webp | Enforced via `is_file_type_allowed()` |
| Max file size | Existing limits apply | Uses existing image processing |

---

## 5. API Specification

### 5.1 New Endpoints

#### 5.1.1 List Recipe Images

```
GET /api/recipe/{recipe_id}/images/
```

**Response:**
```json
[
    {
        "id": 1,
        "image": "/media/recipes/abc123_1.jpg",
        "order": 0,
        "created_at": "2025-12-06T10:00:00Z",
        "created_by": {"id": 1, "display_name": "User"}
    },
    {
        "id": 2,
        "image": "/media/recipes/def456_2.jpg",
        "order": 1,
        "created_at": "2025-12-06T10:01:00Z",
        "created_by": {"id": 1, "display_name": "User"}
    }
]
```

#### 5.1.2 Add Recipe Image

```
POST /api/recipe/{recipe_id}/images/
Content-Type: multipart/form-data
```

**Request Body:**
- `image`: File (required) - The image file to upload
- `image_url`: String (optional) - URL to download image from (alternative to file)

**Response:** `201 Created`
```json
{
    "id": 3,
    "image": "/media/recipes/ghi789_3.jpg",
    "order": 2,
    "created_at": "2025-12-06T10:02:00Z",
    "created_by": {"id": 1, "display_name": "User"}
}
```

**Errors:**
- `400 Bad Request`: Invalid file type or max images reached
- `403 Forbidden`: User lacks permission
- `404 Not Found`: Recipe not found

#### 5.1.3 Update Recipe Image (Reorder)

```
PATCH /api/recipe/{recipe_id}/images/{image_id}/
Content-Type: application/json
```

**Request Body:**
```json
{
    "order": 0
}
```

**Response:** `200 OK`

#### 5.1.4 Delete Recipe Image

```
DELETE /api/recipe/{recipe_id}/images/{image_id}/
```

**Response:** `204 No Content`

#### 5.1.5 Bulk Reorder Images

```
POST /api/recipe/{recipe_id}/images/reorder/
Content-Type: application/json
```

**Request Body:**
```json
{
    "image_ids": [3, 1, 2]
}
```

**Response:** `200 OK`
```json
{
    "status": "success",
    "images": [
        {"id": 3, "order": 0},
        {"id": 1, "order": 1},
        {"id": 2, "order": 2}
    ]
}
```

### 5.2 Modified Endpoints

#### 5.2.1 Recipe Detail (GET /api/recipe/{id}/)

Add `images` field to response:

```json
{
    "id": 42,
    "name": "Chocolate Cake",
    "image": "/media/recipes/main_42.jpg",
    "images": [
        {"id": 1, "image": "/media/recipes/abc_1.jpg", "order": 0},
        {"id": 2, "image": "/media/recipes/def_2.jpg", "order": 1}
    ],
    ...
}
```

#### 5.2.2 Recipe Overview (GET /api/recipe/)

The list endpoint should continue to use only the primary `image` field for performance. No changes required.

### 5.3 Existing Endpoint Behavior

The existing `PUT /api/recipe/{id}/image/` endpoint **remains unchanged**. It continues to update the primary `Recipe.image` field.

---

## 6. Frontend Specification

### 6.1 Component Changes

#### 6.1.1 RecipeImage.vue (Display Component)

**Current:** Displays single image or placeholder.

**Changes:** Add optional prop to display from images array.

```vue
<script setup lang="ts">
const props = defineProps({
    recipe: {type: {} as PropType<Recipe | RecipeOverview>, required: false},
    // NEW: Allow passing specific image URL
    imageUrl: {type: String, required: false},
    // ... existing props
})

const image = computed(() => {
    if (props.imageUrl) {
        return props.imageUrl
    }
    if (props.recipe?.image) {
        return props.recipe.image
    }
    return recipeDefaultImage
})
</script>
```

#### 6.1.2 RecipeView.vue (Recipe Display Page)

**Changes:** Add image gallery when multiple images exist.

```vue
<!-- After primary image display -->
<template v-if="recipe.images && recipe.images.length > 0">
    <recipe-image-gallery
        :images="recipe.images"
        :primary-image="recipe.image"
    />
</template>
```

#### 6.1.3 RecipeEditor.vue (Recipe Edit Page)

**Changes:** Replace single file upload with multi-image manager.

```vue
<!-- Replace existing image upload section (lines 30-48) -->
<recipe-image-manager
    v-model="editingObj.images"
    :recipe-id="editingObj.id"
    :primary-image="editingObj.image"
    @update:primary="updatePrimaryImage"
    :max-images="10"
/>
```

### 6.2 New Components

#### 6.2.1 RecipeImageManager.vue

Multi-image upload and management component for the recipe editor.

**Features:**
- Display grid of current images with thumbnails
- Drag-and-drop reordering (using vue-draggable-plus)
- Delete button on each image
- "Add Image" button (disabled when at max)
- Visual indicator for primary image
- Click to set as primary image

**Props:**
```typescript
interface Props {
    modelValue: RecipeImage[]      // Current images
    recipeId: number | undefined   // Recipe ID (undefined for new recipes)
    primaryImage: string | null    // Current primary image URL
    maxImages: number              // Maximum allowed (default: 10)
    disabled: boolean              // Disable all interactions
}
```

**Events:**
```typescript
interface Events {
    'update:modelValue': RecipeImage[]  // Images changed
    'update:primary': File | string     // Primary image changed
}
```

#### 6.2.2 RecipeImageGallery.vue

Image gallery/carousel component for recipe view page.

**Features:**
- Thumbnail strip showing all images
- Click thumbnail to view full size
- Optional lightbox mode for full-screen viewing
- Swipe support on mobile

**Props:**
```typescript
interface Props {
    images: RecipeImage[]          // Additional images
    primaryImage: string | null    // Primary image URL
}
```

### 6.3 API Composable Changes

#### 6.3.1 useFileApi.ts

Add new functions:

```typescript
/**
 * Get all images for a recipe
 */
function getRecipeImages(recipeId: number): Promise<RecipeImage[]>

/**
 * Add a new image to a recipe
 */
function addRecipeImage(
    recipeId: number,
    file: File | null,
    imageUrl?: string
): Promise<RecipeImage>

/**
 * Delete a recipe image
 */
function deleteRecipeImage(
    recipeId: number,
    imageId: number
): Promise<void>

/**
 * Reorder recipe images
 */
function reorderRecipeImages(
    recipeId: number,
    imageIds: number[]
): Promise<void>
```

### 6.4 TypeScript Types

Add to `vue3/src/openapi/models/`:

```typescript
interface RecipeImage {
    id: number
    image: string
    order: number
    createdAt: Date
    createdBy: User
}
```

Update `Recipe` interface to include:
```typescript
interface Recipe {
    // ... existing fields
    images?: RecipeImage[]
}
```

---

## 7. Implementation Tasks

Each task below is designed to be **self-contained** and can be assigned to an independent agent. Tasks include full context and acceptance criteria.

---

### Task 1: Create RecipeImage Django Model

**Priority:** 1 (Must be done first)
**Estimated Complexity:** Low
**Dependencies:** None

#### Context

Tandoor is a Django-based recipe management application. Models are defined in `cookbook/models.py`. The project uses:
- `ScopedManager` from django-scopes for multi-tenancy (all models are scoped to a `Space`)
- `PermissionModelMixin` for permission handling
- `ExportModelOperationsMixin` for prometheus metrics

The `Recipe` model is defined at line 1084 of `cookbook/models.py`. It has a `space` ForeignKey for multi-tenancy.

#### Task Description

Create a new `RecipeImage` model in `cookbook/models.py` that stores additional images for recipes.

#### Requirements

1. Add the model after the `Recipe` class (around line 1143)
2. Include these fields:
   - `recipe`: ForeignKey to Recipe with CASCADE delete and `related_name='images'`
   - `image`: ImageField with `upload_to='recipes/'`
   - `order`: IntegerField with default=0
   - `created_at`: DateTimeField with auto_now_add=True
   - `created_by`: ForeignKey to User with CASCADE delete
   - `space`: ForeignKey to Space with CASCADE delete
3. Add `ScopedManager(space='space')` as `objects`
4. Add `PermissionModelMixin` and `ExportModelOperationsMixin('recipe_image')`
5. Implement `get_space_key()` returning `('recipe', 'space')`
6. Implement `get_space()` returning `self.recipe.space`
7. Set `Meta.ordering` to `['order', 'created_at']`
8. Add an index on `['recipe', 'order']`

#### Reference Code Pattern

Look at the `Comment` model (line 1145) for a similar pattern of a model with ForeignKey to Recipe:

```python
class Comment(ExportModelOperationsMixin('comment'), models.Model, PermissionModelMixin):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    # ...
    objects = ScopedManager(space='recipe__space')

    @staticmethod
    def get_space_key():
        return 'recipe', 'space'

    def get_space(self):
        return self.recipe.space
```

#### Acceptance Criteria

- [ ] Model is added to `cookbook/models.py`
- [ ] Model follows existing code style and patterns
- [ ] Model includes all required fields
- [ ] Model includes proper Meta class with ordering and indexes
- [ ] Model includes ScopedManager for multi-tenancy
- [ ] Model can be imported without errors

#### Files to Modify

- `cookbook/models.py`

---

### Task 2: Create Database Migration

**Priority:** 2
**Estimated Complexity:** Low
**Dependencies:** Task 1

#### Context

Django uses migrations to manage database schema changes. Migrations are stored in `cookbook/migrations/`. The latest migration is `0234_alter_shoppinglist_options_and_more.py`.

#### Task Description

Create a Django migration for the new `RecipeImage` model.

#### Requirements

1. Run `python manage.py makemigrations cookbook` to generate the migration
2. The migration should create the `RecipeImage` table with all fields and indexes
3. Migration number should be `0235` or higher

#### Acceptance Criteria

- [ ] Migration file is created in `cookbook/migrations/`
- [ ] Migration creates the `cookbook_recipeimage` table
- [ ] Migration includes index on `['recipe', 'order']`
- [ ] Migration can be applied without errors: `python manage.py migrate`
- [ ] Migration can be reversed without errors: `python manage.py migrate cookbook <previous_migration>`

#### Files to Create

- `cookbook/migrations/0235_recipeimage.py` (or next available number)

#### Commands to Run

```bash
cd /home/user/tandoor
python manage.py makemigrations cookbook --name recipeimage
python manage.py migrate
```

---

### Task 3: Create RecipeImage Serializer

**Priority:** 3
**Estimated Complexity:** Medium
**Dependencies:** Task 1

#### Context

Tandoor uses Django REST Framework for its API. Serializers are defined in `cookbook/serializer.py`. The project uses:
- `SpacedModelSerializer` as base class for space-scoped models
- `WritableNestedModelSerializer` for nested object creation
- Custom validation in serializers

The existing `RecipeImageSerializer` (line 1223) handles the single `Recipe.image` field. We need a NEW serializer for the `RecipeImage` model.

#### Task Description

Create a serializer for the `RecipeImage` model in `cookbook/serializer.py`.

#### Requirements

1. Create `RecipeImageSerializer` class (rename existing one to `RecipePrimaryImageSerializer` first)
2. Base class should be `SpacedModelSerializer`
3. Fields: `id`, `image`, `order`, `created_at`, `created_by` (read-only)
4. Add `image_url` write-only field for URL-based image upload
5. Add validation to check file type using existing `is_file_type_allowed()` function
6. Add validation to limit maximum 10 images per recipe

#### Validation Logic

```python
def validate(self, attrs):
    # Check max images limit
    recipe = self.context.get('recipe')
    if recipe:
        current_count = RecipeImage.objects.filter(recipe=recipe).count()
        if current_count >= 10:
            raise serializers.ValidationError("Maximum 10 images per recipe allowed")

    # Check file type
    if 'image' in attrs:
        if not is_file_type_allowed(attrs['image'].name, image_only=True):
            raise serializers.ValidationError("Invalid image file type")

    return attrs
```

#### Reference

Look at `UserFileSerializer` (line 267) for a similar file upload serializer pattern.

#### Acceptance Criteria

- [ ] Serializer is added to `cookbook/serializer.py`
- [ ] Existing `RecipeImageSerializer` is renamed to `RecipePrimaryImageSerializer`
- [ ] All references to old `RecipeImageSerializer` are updated
- [ ] New serializer validates file types
- [ ] New serializer enforces 10 image limit
- [ ] Serializer includes `image_url` field for URL uploads

#### Files to Modify

- `cookbook/serializer.py`
- `cookbook/views/api.py` (update reference to renamed serializer)

---

### Task 4: Update Recipe Serializer to Include Images

**Priority:** 4
**Estimated Complexity:** Low
**Dependencies:** Task 3

#### Context

The `RecipeSerializer` is defined at line 1300+ of `cookbook/serializer.py`. It serializes the full Recipe object for detail views. The `RecipeOverviewSerializer` is used for list views and should NOT include the images array for performance.

#### Task Description

Update the `RecipeSerializer` to include the `images` field.

#### Requirements

1. Add `images` field to `RecipeSerializer` using the new `RecipeImageSerializer`
2. Make `images` a nested serializer with `many=True` and `read_only=True`
3. Add `images` to the `Meta.fields` list
4. Do NOT add `images` to `RecipeOverviewSerializer` (performance)

#### Code to Add

```python
class RecipeSerializer(...):
    # ... existing fields
    images = RecipeImageSerializer(many=True, read_only=True)

    class Meta:
        model = Recipe
        fields = [..., 'images']  # Add 'images' to existing fields
```

#### Acceptance Criteria

- [ ] `RecipeSerializer` includes `images` field
- [ ] `images` field is read-only
- [ ] `RecipeOverviewSerializer` does NOT include `images`
- [ ] Recipe detail API returns `images` array

#### Files to Modify

- `cookbook/serializer.py`

---

### Task 5: Create RecipeImage ViewSet

**Priority:** 5
**Estimated Complexity:** High
**Dependencies:** Task 3

#### Context

API views are defined in `cookbook/views/api.py`. The project uses:
- `viewsets.ModelViewSet` as base class
- `@decorators.action` for custom endpoints
- `MultiPartParser` for file uploads
- Permission checking via `obj.get_space() != request.space`

The existing recipe image upload is at line 1635 as `RecipeViewSet.image()` method.

#### Task Description

Create a new ViewSet for managing recipe images with CRUD operations and bulk reorder.

#### Requirements

1. Create `RecipeImageViewSet` class
2. Implement these endpoints:
   - `GET /api/recipe/{recipe_id}/images/` - List all images for a recipe
   - `POST /api/recipe/{recipe_id}/images/` - Add new image
   - `PATCH /api/recipe/{recipe_id}/images/{id}/` - Update image (reorder)
   - `DELETE /api/recipe/{recipe_id}/images/{id}/` - Delete image
   - `POST /api/recipe/{recipe_id}/images/reorder/` - Bulk reorder

3. Use `MultiPartParser` for POST endpoint
4. Include permission checking (user must have access to recipe's space)
5. Use existing `handle_image()` function from `cookbook/helper/image_processing.py` for image processing
6. Auto-assign `order` on create (max existing order + 1)
7. Auto-assign `space` and `created_by` from request context

#### Code Structure

```python
class RecipeImageViewSet(viewsets.ModelViewSet):
    serializer_class = RecipeImageSerializer
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        recipe_id = self.kwargs.get('recipe_pk')
        return RecipeImage.objects.filter(recipe_id=recipe_id)

    def get_recipe(self):
        recipe_id = self.kwargs.get('recipe_pk')
        recipe = get_object_or_404(Recipe, pk=recipe_id)
        if recipe.get_space() != self.request.space:
            raise PermissionDenied()
        return recipe

    def perform_create(self, serializer):
        recipe = self.get_recipe()
        # Get next order value
        max_order = RecipeImage.objects.filter(recipe=recipe).aggregate(
            Max('order'))['order__max'] or -1

        # Handle image processing (similar to RecipeViewSet.image())
        # ...

        serializer.save(
            recipe=recipe,
            space=recipe.space,
            created_by=self.request.user,
            order=max_order + 1
        )

    @decorators.action(detail=False, methods=['POST'])
    def reorder(self, request, recipe_pk=None):
        recipe = self.get_recipe()
        image_ids = request.data.get('image_ids', [])

        # Validate all IDs belong to this recipe
        images = RecipeImage.objects.filter(recipe=recipe, id__in=image_ids)
        if images.count() != len(image_ids):
            return Response({'error': 'Invalid image IDs'}, status=400)

        # Update order
        for order, image_id in enumerate(image_ids):
            RecipeImage.objects.filter(id=image_id).update(order=order)

        return Response({'status': 'success'})
```

#### Reference

Look at existing `RecipeViewSet.image()` method (line 1635) for image handling pattern.

#### Acceptance Criteria

- [ ] ViewSet is added to `cookbook/views/api.py`
- [ ] All CRUD operations work correctly
- [ ] Bulk reorder endpoint works
- [ ] Permission checking is implemented
- [ ] Image processing uses existing `handle_image()` function
- [ ] Images are saved with UUID filenames
- [ ] 10 image limit is enforced

#### Files to Modify

- `cookbook/views/api.py`

---

### Task 6: Register API Routes

**Priority:** 6
**Estimated Complexity:** Low
**Dependencies:** Task 5

#### Context

URL routing is defined in `cookbook/urls.py`. The project uses Django REST Framework's router for automatic URL generation. Nested routes (like `/recipe/{id}/images/`) require special handling.

#### Task Description

Register the new `RecipeImageViewSet` with nested routing under recipes.

#### Requirements

1. Register nested routes for recipe images
2. URLs should be:
   - `/api/recipe/{recipe_pk}/images/`
   - `/api/recipe/{recipe_pk}/images/{pk}/`
   - `/api/recipe/{recipe_pk}/images/reorder/`

#### Implementation Options

**Option A: Use drf-nested-routers (if available)**

```python
from rest_framework_nested import routers

router = routers.DefaultRouter()
router.register(r'recipe', api.RecipeViewSet)

recipe_router = routers.NestedDefaultRouter(router, r'recipe', lookup='recipe')
recipe_router.register(r'images', api.RecipeImageViewSet, basename='recipe-images')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/', include(recipe_router.urls)),
]
```

**Option B: Manual URL patterns**

```python
urlpatterns = [
    # ... existing patterns
    path('api/recipe/<int:recipe_pk>/images/',
         api.RecipeImageViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='recipe-images-list'),
    path('api/recipe/<int:recipe_pk>/images/<int:pk>/',
         api.RecipeImageViewSet.as_view({'patch': 'partial_update', 'delete': 'destroy'}),
         name='recipe-images-detail'),
    path('api/recipe/<int:recipe_pk>/images/reorder/',
         api.RecipeImageViewSet.as_view({'post': 'reorder'}),
         name='recipe-images-reorder'),
]
```

#### Acceptance Criteria

- [ ] API routes are registered in `cookbook/urls.py`
- [ ] Routes work correctly with recipe ID parameter
- [ ] All HTTP methods route to correct ViewSet methods
- [ ] Routes don't conflict with existing routes

#### Files to Modify

- `cookbook/urls.py`

---

### Task 7: Add RecipeImage to Django Admin

**Priority:** 7
**Estimated Complexity:** Low
**Dependencies:** Task 1

#### Context

Django admin configuration is in `cookbook/admin.py`. The project registers models with the admin site for management purposes.

#### Task Description

Add `RecipeImage` model to Django admin for debugging and management.

#### Requirements

1. Create `RecipeImageAdmin` class
2. Display: `id`, `recipe`, `order`, `created_at`, `created_by`
3. Add list filters: `recipe`, `space`, `created_by`
4. Add search fields: `recipe__name`
5. Make `created_at` and `created_by` read-only

#### Code

```python
@admin.register(RecipeImage)
class RecipeImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipe', 'order', 'created_at', 'created_by')
    list_filter = ('space', 'created_by')
    search_fields = ('recipe__name',)
    readonly_fields = ('created_at', 'created_by')
    ordering = ('recipe', 'order')
```

#### Acceptance Criteria

- [ ] `RecipeImage` appears in Django admin
- [ ] Admin displays correct fields
- [ ] Filtering and search work
- [ ] Can view/edit/delete images from admin

#### Files to Modify

- `cookbook/admin.py`

---

### Task 8: Create RecipeImageManager Vue Component

**Priority:** 8
**Estimated Complexity:** High
**Dependencies:** Task 5, Task 6

#### Context

The frontend uses Vue 3 with Vuetify 3 and TypeScript. Components are organized in:
- `vue3/src/components/display/` - Display components
- `vue3/src/components/inputs/` - Input/form components
- `vue3/src/components/model_editors/` - Model editing components

The project uses:
- `vue-draggable-plus` for drag-and-drop
- `VFileUpload` from Vuetify labs for file upload
- Composition API with `<script setup>`

The current single-image upload is in `RecipeEditor.vue` (lines 30-48).

#### Task Description

Create a new `RecipeImageManager.vue` component for managing multiple recipe images.

#### Requirements

1. Create component at `vue3/src/components/inputs/RecipeImageManager.vue`
2. Display grid of image thumbnails
3. Support drag-and-drop reordering using `vue-draggable-plus`
4. Delete button on each image
5. "Add Image" button with file picker
6. Show count (e.g., "3/10 images")
7. Disable add when at max (10 images)
8. Loading state during upload/delete operations

#### Component Template Structure

```vue
<template>
    <v-card variant="outlined">
        <v-card-title class="d-flex align-center">
            <span>{{ $t('Images') }}</span>
            <v-spacer></v-spacer>
            <span class="text-caption">{{ images.length }}/{{ maxImages }}</span>
        </v-card-title>

        <v-card-text>
            <!-- Draggable image grid -->
            <vue-draggable
                v-model="localImages"
                handle=".drag-handle"
                @end="onReorder"
                class="d-flex flex-wrap ga-2"
            >
                <div v-for="(img, index) in localImages" :key="img.id" class="position-relative">
                    <v-img
                        :src="img.image"
                        width="120"
                        height="120"
                        cover
                        class="rounded"
                    >
                        <div class="image-overlay d-flex align-center justify-center">
                            <v-btn
                                icon="$delete"
                                size="small"
                                color="error"
                                @click="deleteImage(img.id)"
                            ></v-btn>
                            <v-icon class="drag-handle ml-2" icon="$dragHandle"></v-icon>
                        </div>
                    </v-img>
                </div>
            </vue-draggable>

            <!-- Add image button -->
            <v-file-upload
                v-if="images.length < maxImages"
                v-model="newFile"
                :title="$t('Add_Image')"
                :disabled="loading || images.length >= maxImages"
                accept="image/*"
                @update:model-value="uploadImage"
            />
        </v-card-text>
    </v-card>
</template>
```

#### Props and Events

```typescript
interface Props {
    modelValue: RecipeImage[]
    recipeId: number | undefined
    maxImages?: number  // default: 10
    disabled?: boolean
}

interface Emits {
    (e: 'update:modelValue', value: RecipeImage[]): void
}
```

#### Acceptance Criteria

- [ ] Component created at correct path
- [ ] Displays existing images in grid
- [ ] Drag-and-drop reordering works
- [ ] Delete button removes image
- [ ] Add button uploads new image
- [ ] Counter shows current/max
- [ ] Add disabled at max images
- [ ] Loading state shown during operations
- [ ] Uses existing Vuetify styling patterns

#### Files to Create

- `vue3/src/components/inputs/RecipeImageManager.vue`

---

### Task 9: Create RecipeImageGallery Vue Component

**Priority:** 9
**Estimated Complexity:** Medium
**Dependencies:** None (can be done in parallel with Task 8)

#### Context

This component displays images on the recipe view page. It should show thumbnails and allow users to view full-size images.

#### Task Description

Create a `RecipeImageGallery.vue` component for displaying multiple recipe images.

#### Requirements

1. Create component at `vue3/src/components/display/RecipeImageGallery.vue`
2. Display horizontal thumbnail strip
3. Click thumbnail to view larger image
4. Support lightbox/modal for full-screen viewing
5. Include primary image in the gallery (first position)
6. Mobile-friendly (touch/swipe support optional for MVP)

#### Component Template Structure

```vue
<template>
    <v-card v-if="allImages.length > 1" class="mt-2">
        <v-card-title>{{ $t('Images') }}</v-card-title>
        <v-card-text>
            <div class="d-flex overflow-x-auto ga-2 pb-2">
                <v-img
                    v-for="(img, index) in allImages"
                    :key="index"
                    :src="img"
                    width="100"
                    height="100"
                    cover
                    class="rounded cursor-pointer flex-shrink-0"
                    @click="openLightbox(index)"
                />
            </div>
        </v-card-text>
    </v-card>

    <!-- Lightbox dialog -->
    <v-dialog v-model="lightboxOpen" max-width="90vw">
        <v-card>
            <v-img :src="allImages[selectedIndex]" max-height="80vh" contain />
            <v-card-actions>
                <v-btn @click="prev" :disabled="selectedIndex === 0">
                    <v-icon>fa-solid fa-chevron-left</v-icon>
                </v-btn>
                <v-spacer></v-spacer>
                <span>{{ selectedIndex + 1 }} / {{ allImages.length }}</span>
                <v-spacer></v-spacer>
                <v-btn @click="next" :disabled="selectedIndex === allImages.length - 1">
                    <v-icon>fa-solid fa-chevron-right</v-icon>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>
```

#### Props

```typescript
interface Props {
    images: RecipeImage[]       // Additional images from API
    primaryImage: string | null // Primary image URL
}
```

#### Acceptance Criteria

- [ ] Component created at correct path
- [ ] Shows horizontal thumbnail strip
- [ ] Includes primary image first
- [ ] Click opens lightbox view
- [ ] Navigation between images works
- [ ] Only shows when > 1 image total
- [ ] Responsive on mobile

#### Files to Create

- `vue3/src/components/display/RecipeImageGallery.vue`

---

### Task 10: Add API Functions to useFileApi.ts

**Priority:** 10
**Estimated Complexity:** Medium
**Dependencies:** Task 5, Task 6

#### Context

API functions for file operations are in `vue3/src/composables/useFileApi.ts`. The file uses:
- `fetch()` for API calls
- `getCookie('csrftoken')` for CSRF tokens
- `getDjangoUrl()` for URL building
- `FormData` for file uploads

#### Task Description

Add functions for recipe image CRUD operations to the `useFileApi` composable.

#### Requirements

1. Add `getRecipeImages(recipeId)` function
2. Add `addRecipeImage(recipeId, file, imageUrl?)` function
3. Add `deleteRecipeImage(recipeId, imageId)` function
4. Add `reorderRecipeImages(recipeId, imageIds)` function
5. All functions should handle errors appropriately
6. Return type-safe responses using OpenAPI types

#### Code to Add

```typescript
/**
 * Get all images for a recipe
 */
function getRecipeImages(recipeId: number): Promise<RecipeImage[]> {
    return fetch(getDjangoUrl(`api/recipe/${recipeId}/images/`), {
        method: 'GET',
        headers: {'X-CSRFToken': getCookie('csrftoken')},
    }).then(r => {
        if (!r.ok) throw new ResponseError(r)
        return r.json()
    })
}

/**
 * Add a new image to a recipe
 */
function addRecipeImage(
    recipeId: number,
    file: File | null,
    imageUrl?: string
): Promise<RecipeImage> {
    let formData = new FormData()
    if (file != null) {
        formData.append('image', file)
    }
    if (imageUrl) {
        formData.append('image_url', imageUrl)
    }

    return fetch(getDjangoUrl(`api/recipe/${recipeId}/images/`), {
        method: 'POST',
        headers: {'X-CSRFToken': getCookie('csrftoken')},
        body: formData
    }).then(r => {
        if (!r.ok) throw new ResponseError(r)
        return r.json()
    })
}

/**
 * Delete a recipe image
 */
function deleteRecipeImage(recipeId: number, imageId: number): Promise<void> {
    return fetch(getDjangoUrl(`api/recipe/${recipeId}/images/${imageId}/`), {
        method: 'DELETE',
        headers: {'X-CSRFToken': getCookie('csrftoken')},
    }).then(r => {
        if (!r.ok) throw new ResponseError(r)
    })
}

/**
 * Reorder recipe images
 */
function reorderRecipeImages(recipeId: number, imageIds: number[]): Promise<void> {
    return fetch(getDjangoUrl(`api/recipe/${recipeId}/images/reorder/`), {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ image_ids: imageIds })
    }).then(r => {
        if (!r.ok) throw new ResponseError(r)
    })
}
```

#### Acceptance Criteria

- [ ] All four functions added to `useFileApi.ts`
- [ ] Functions exported from composable
- [ ] Error handling implemented
- [ ] TypeScript types correct
- [ ] Functions work with API endpoints

#### Files to Modify

- `vue3/src/composables/useFileApi.ts`

---

### Task 11: Update RecipeEditor.vue for Multi-Image Support

**Priority:** 11
**Estimated Complexity:** Medium
**Dependencies:** Task 8, Task 10

#### Context

`RecipeEditor.vue` is located at `vue3/src/components/model_editors/RecipeEditor.vue`. It currently has a single file upload section (lines 30-48) for the primary image.

#### Task Description

Update RecipeEditor to use the new RecipeImageManager component alongside the existing primary image upload.

#### Requirements

1. Keep existing primary image upload functionality (lines 30-48)
2. Add RecipeImageManager below primary image section
3. Only show RecipeImageManager for existing recipes (`isUpdate()` is true)
4. Pass recipe's images to the manager
5. Handle loading states

#### Code Changes

After the existing image section (around line 48), add:

```vue
<!-- Multi-image manager (only for existing recipes) -->
<template v-if="isUpdate() && editingObj.id">
    <v-divider class="my-4"></v-divider>
    <recipe-image-manager
        v-model="editingObj.images"
        :recipe-id="editingObj.id"
        :disabled="loading || fileApiLoading"
    />
</template>
```

Import the component:

```typescript
import RecipeImageManager from "@/components/inputs/RecipeImageManager.vue"
```

#### Acceptance Criteria

- [ ] RecipeImageManager imported and used
- [ ] Only shows for existing recipes
- [ ] Passes correct props
- [ ] Loading states work correctly
- [ ] Primary image upload still works
- [ ] No visual regression

#### Files to Modify

- `vue3/src/components/model_editors/RecipeEditor.vue`

---

### Task 12: Update RecipeView.vue for Image Gallery

**Priority:** 12
**Estimated Complexity:** Low
**Dependencies:** Task 9

#### Context

`RecipeView.vue` is located at `vue3/src/components/display/RecipeView.vue`. It displays the recipe details and currently shows the primary image.

#### Task Description

Add the RecipeImageGallery component to display additional images.

#### Requirements

1. Import and add RecipeImageGallery component
2. Place it after the primary image display
3. Pass recipe.images and recipe.image as props
4. Only render when recipe has additional images

#### Code Changes

Around line 120 (after the desktop layout section), add:

```vue
<!-- Image gallery for additional images -->
<recipe-image-gallery
    v-if="recipe.images && recipe.images.length > 0"
    :images="recipe.images"
    :primary-image="recipe.image"
/>
```

Import the component:

```typescript
import RecipeImageGallery from "@/components/display/RecipeImageGallery.vue"
```

#### Acceptance Criteria

- [ ] RecipeImageGallery imported and used
- [ ] Only shows when additional images exist
- [ ] Displays correctly on desktop and mobile
- [ ] Primary image still displays normally

#### Files to Modify

- `vue3/src/components/display/RecipeView.vue`

---

### Task 13: Add TypeScript Types for RecipeImage

**Priority:** 13 (can be done early, in parallel)
**Estimated Complexity:** Low
**Dependencies:** None

#### Context

TypeScript types are auto-generated from the OpenAPI schema in `vue3/src/openapi/models/`. However, since we're adding a new model, we may need to manually add types until the schema is regenerated.

#### Task Description

Add TypeScript interface for RecipeImage and update Recipe interface.

#### Requirements

1. Create or update `RecipeImage` interface
2. Update `Recipe` interface to include optional `images` array
3. Ensure types match API response structure

#### Code

Create `vue3/src/openapi/models/RecipeImage.ts`:

```typescript
import { User } from './User'

export interface RecipeImage {
    id: number
    image: string
    order: number
    createdAt: Date
    createdBy: User
}

export function RecipeImageFromJSON(json: any): RecipeImage {
    return {
        id: json['id'],
        image: json['image'],
        order: json['order'],
        createdAt: new Date(json['created_at']),
        createdBy: json['created_by'],
    }
}

export function RecipeImageToJSON(value: RecipeImage): any {
    return {
        id: value.id,
        image: value.image,
        order: value.order,
    }
}
```

Update Recipe interface to include:
```typescript
images?: RecipeImage[]
```

#### Acceptance Criteria

- [ ] RecipeImage interface created
- [ ] Recipe interface updated
- [ ] Types exported correctly
- [ ] No TypeScript errors

#### Files to Create/Modify

- `vue3/src/openapi/models/RecipeImage.ts` (create)
- `vue3/src/openapi/models/Recipe.ts` (modify)
- `vue3/src/openapi/models/index.ts` (add export)

---

### Task 14: Add Internationalization Strings

**Priority:** 14
**Estimated Complexity:** Low
**Dependencies:** None (can be done in parallel)

#### Context

Translations are stored in `vue3/src/locales/` as JSON files. The primary language is English (`en.json`). Other language files can be updated later.

#### Task Description

Add English translation strings for the multi-image feature.

#### Requirements

1. Add new translation keys to `vue3/src/locales/en.json`
2. Keys should follow existing naming conventions

#### Strings to Add

```json
{
    "Images": "Images",
    "Add_Image": "Add Image",
    "Delete_Image": "Delete Image",
    "Reorder_Images": "Reorder Images",
    "Max_Images_Reached": "Maximum images reached ({count}/{max})",
    "Image_Upload_Error": "Failed to upload image",
    "Image_Delete_Error": "Failed to delete image",
    "Image_Reorder_Error": "Failed to reorder images",
    "View_All_Images": "View All Images"
}
```

#### Acceptance Criteria

- [ ] Strings added to `en.json`
- [ ] Keys follow existing conventions
- [ ] No JSON syntax errors
- [ ] Strings used in components reference these keys

#### Files to Modify

- `vue3/src/locales/en.json`

---

### Task 15: Write Backend Unit Tests

**Priority:** 15
**Estimated Complexity:** Medium
**Dependencies:** Tasks 1-6

#### Context

Tests are in `cookbook/tests/`. The project uses pytest with factory_boy for fixtures. Test files follow the pattern `test_*.py`.

#### Task Description

Write unit tests for the RecipeImage model and API.

#### Requirements

1. Create `cookbook/tests/test_recipe_images.py`
2. Test model creation and relationships
3. Test API endpoints (CRUD operations)
4. Test 10 image limit validation
5. Test permission checking
6. Test reorder functionality

#### Test Cases

```python
import pytest
from cookbook.models import Recipe, RecipeImage
from cookbook.tests.factories import RecipeFactory, UserFactory, SpaceFactory

@pytest.mark.django_db
class TestRecipeImageModel:
    def test_create_recipe_image(self):
        """Test creating a recipe image"""
        pass

    def test_recipe_image_ordering(self):
        """Test images are ordered by order field"""
        pass

    def test_cascade_delete(self):
        """Test images are deleted when recipe is deleted"""
        pass

@pytest.mark.django_db
class TestRecipeImageAPI:
    def test_list_images(self, api_client, recipe):
        """Test listing recipe images"""
        pass

    def test_add_image(self, api_client, recipe):
        """Test adding an image to recipe"""
        pass

    def test_add_image_max_limit(self, api_client, recipe):
        """Test 10 image limit is enforced"""
        pass

    def test_delete_image(self, api_client, recipe_image):
        """Test deleting a recipe image"""
        pass

    def test_reorder_images(self, api_client, recipe):
        """Test reordering recipe images"""
        pass

    def test_permission_denied_other_space(self, api_client, other_space_recipe):
        """Test cannot access images from other space"""
        pass
```

#### Acceptance Criteria

- [ ] Test file created
- [ ] All test cases implemented
- [ ] Tests pass: `pytest cookbook/tests/test_recipe_images.py`
- [ ] Tests cover happy path and error cases
- [ ] Tests check permissions

#### Files to Create

- `cookbook/tests/test_recipe_images.py`

---

### Task 16: Write Frontend Component Tests

**Priority:** 16
**Estimated Complexity:** Medium
**Dependencies:** Tasks 8, 9

#### Context

Frontend tests would typically be in `vue3/src/components/__tests__/` using Vitest and Vue Test Utils.

#### Task Description

Write component tests for RecipeImageManager and RecipeImageGallery.

#### Requirements

1. Test RecipeImageManager renders correctly
2. Test delete button triggers delete
3. Test add image triggers upload
4. Test reorder emits correct event
5. Test RecipeImageGallery renders thumbnails
6. Test lightbox opens on click

#### Acceptance Criteria

- [ ] Tests created for both components
- [ ] Tests pass
- [ ] Cover key functionality

#### Files to Create

- `vue3/src/components/inputs/__tests__/RecipeImageManager.spec.ts`
- `vue3/src/components/display/__tests__/RecipeImageGallery.spec.ts`

---

## 8. Testing Requirements

### 8.1 Manual Testing Checklist

Before considering the feature complete, manually verify:

- [ ] Can upload image to new recipe (after first save)
- [ ] Can upload multiple images to existing recipe
- [ ] Can delete individual images
- [ ] Can reorder images via drag-and-drop
- [ ] Primary image displays correctly on recipe cards
- [ ] Image gallery shows on recipe view page
- [ ] Lightbox opens and navigation works
- [ ] Cannot add more than 10 images
- [ ] Images persist after page reload
- [ ] Works on mobile devices
- [ ] Works with existing recipes (backward compatibility)
- [ ] No errors in browser console
- [ ] No errors in Django logs

### 8.2 Edge Cases to Test

- Recipe with 0 images
- Recipe with exactly 1 image (primary only)
- Recipe with exactly 10 images
- Uploading invalid file type
- Uploading very large image (tests compression)
- Deleting all images
- Rapid sequential uploads
- Concurrent uploads
- Network failure during upload
- Permission denied scenarios

---

## 9. Migration Strategy

### 9.1 Data Migration

Existing recipes have images stored in `Recipe.image`. This field is **retained** for backward compatibility. No data migration is strictly required.

### 9.2 Deployment Steps

1. Deploy backend changes (model, migrations, API)
2. Run migrations: `python manage.py migrate`
3. Deploy frontend changes
4. Clear any caches if needed

### 9.3 Rollback Plan

If issues are discovered:
1. The `Recipe.image` field is unchanged, so primary images continue to work
2. The `RecipeImage` table can be dropped if needed
3. Frontend changes can be reverted independently

---

## Appendix A: File Reference

### Backend Files

| File | Description |
|------|-------------|
| `cookbook/models.py` | Django models |
| `cookbook/serializer.py` | DRF serializers |
| `cookbook/views/api.py` | API ViewSets |
| `cookbook/urls.py` | URL routing |
| `cookbook/admin.py` | Django admin |
| `cookbook/helper/image_processing.py` | Image processing utilities |
| `cookbook/migrations/` | Database migrations |
| `cookbook/tests/` | Backend tests |

### Frontend Files

| File | Description |
|------|-------------|
| `vue3/src/components/display/RecipeImage.vue` | Single image display |
| `vue3/src/components/display/RecipeView.vue` | Recipe view page |
| `vue3/src/components/model_editors/RecipeEditor.vue` | Recipe edit form |
| `vue3/src/composables/useFileApi.ts` | File upload API functions |
| `vue3/src/openapi/models/` | TypeScript types |
| `vue3/src/locales/en.json` | English translations |

---

## Appendix B: Future Enhancements

These items are explicitly out of scope for MVP but documented for future consideration:

1. **Image Captions/Alt Text**: Add `caption` and `alt_text` fields to RecipeImage
2. **Multi-image Import**: Support importing multiple images from recipe URLs
3. **Multi-image Export**: Include all images in recipe exports
4. **Image Cropping**: Allow users to crop images in the editor
5. **AI Image Tagging**: Use AI to auto-tag images (e.g., "finished dish", "ingredients", "step 3")
6. **S3 Optimization**: Implement image thumbnails and CDN caching for S3 deployments
7. **Bulk Upload**: Upload multiple images at once via drag-and-drop
8. **Image Compression Settings**: Let users choose compression level

---

## Appendix C: API Response Examples

### GET /api/recipe/42/

```json
{
    "id": 42,
    "name": "Chocolate Cake",
    "description": "A delicious chocolate cake",
    "image": "/media/recipes/abc123_42.jpg",
    "images": [
        {
            "id": 1,
            "image": "/media/recipes/img1_1.jpg",
            "order": 0,
            "created_at": "2025-12-06T10:00:00Z",
            "created_by": {"id": 1, "display_name": "John"}
        },
        {
            "id": 2,
            "image": "/media/recipes/img2_2.jpg",
            "order": 1,
            "created_at": "2025-12-06T10:05:00Z",
            "created_by": {"id": 1, "display_name": "John"}
        }
    ],
    "steps": [...],
    "keywords": [...]
}
```

### POST /api/recipe/42/images/

Request:
```
Content-Type: multipart/form-data
image: <file>
```

Response (201):
```json
{
    "id": 3,
    "image": "/media/recipes/img3_3.jpg",
    "order": 2,
    "created_at": "2025-12-06T10:10:00Z",
    "created_by": {"id": 1, "display_name": "John"}
}
```

### POST /api/recipe/42/images/reorder/

Request:
```json
{
    "image_ids": [2, 3, 1]
}
```

Response (200):
```json
{
    "status": "success",
    "images": [
        {"id": 2, "order": 0},
        {"id": 3, "order": 1},
        {"id": 1, "order": 2}
    ]
}
```

---

*End of Specification*
