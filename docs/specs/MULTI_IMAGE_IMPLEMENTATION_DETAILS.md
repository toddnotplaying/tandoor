# Multi-Image Recipe: Complete Implementation Details

This document supplements `MULTI_IMAGE_RECIPE_SPECIFICATION.md` with complete, copy-paste ready code implementations.

---

## Task 0: Environment Setup (NEW - Do First)

### Prerequisites
- Docker installed
- Repository cloned

### Setup Commands

```bash
# 1. Navigate to project
cd /home/user/tandoor

# 2. Check if containers exist and start them
# (Actual command depends on your docker setup - check docs.tandoor.dev)

# 3. Run Django development server directly (if not using Docker)
python manage.py runserver 0.0.0.0:8000

# 4. Apply migrations
python manage.py migrate

# 5. Create superuser (if needed)
python manage.py createsuperuser

# 6. Run Vue frontend
cd vue3
npm install
npm run dev
# Frontend runs on http://localhost:5173

# 7. Run backend tests
pytest cookbook/tests/ -v

# 8. Run specific test file
pytest cookbook/tests/test_recipe_images.py -v
```

### Verification Checklist
- [ ] Backend accessible at http://localhost:8000
- [ ] Admin accessible at http://localhost:8000/admin/
- [ ] API returns data at http://localhost:8000/api/recipe/
- [ ] Vue dev server runs without errors
- [ ] Can log in with test user

---

## Task 1: Model - Complete Code

Add this to `cookbook/models.py` after the `Recipe` class (around line 1143):

```python
class RecipeImage(ExportModelOperationsMixin('recipe_image'), models.Model, PermissionModelMixin):
    """
    Stores multiple images for a recipe with ordering support.
    Maximum 10 images per recipe (enforced in serializer/view).
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

    def __str__(self):
        return f"Image {self.order} for {self.recipe.name}"

    class Meta:
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['recipe', 'order']),
        ]
```

### Verification
```bash
python manage.py makemigrations cookbook --name recipeimage
python manage.py migrate
python manage.py shell -c "from cookbook.models import RecipeImage; print('OK')"
```

---

## Task 3: Serializer - Complete Code

### Step 1: Rename existing serializer

In `cookbook/serializer.py`, find `RecipeImageSerializer` (around line 1223) and rename it:

```python
# OLD NAME - RENAME THIS:
# class RecipeImageSerializer(WritableNestedModelSerializer):

# NEW NAME:
class RecipePrimaryImageSerializer(WritableNestedModelSerializer):
    """Serializer for the primary Recipe.image field (backward compatibility)."""
    image = serializers.ImageField(required=False, allow_null=True)
    image_url = serializers.CharField(max_length=4096, required=False, allow_null=True)

    def create(self, validated_data):
        if 'image' in validated_data and not is_file_type_allowed(validated_data['image'].name, image_only=True):
            return None
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'image' in validated_data and not is_file_type_allowed(validated_data['image'].name, image_only=True):
            return None
        return super().update(instance, validated_data)

    class Meta:
        model = Recipe
        fields = ['image', 'image_url', ]
```

### Step 2: Update reference in api.py

In `cookbook/views/api.py`, around line 1635, update the decorator:

```python
# Change this line:
@decorators.action(detail=True, methods=['PUT'], serializer_class=RecipePrimaryImageSerializer,
                   parser_classes=[MultiPartParser], )
def image(self, request, pk):
    # ... rest unchanged
```

### Step 3: Add new RecipeImageSerializer

Add this NEW class in `cookbook/serializer.py` (after the renamed one):

```python
class RecipeImageSerializer(SpacedModelSerializer):
    """
    Serializer for RecipeImage model (multiple images per recipe).
    Used by RecipeImageViewSet for CRUD operations.
    """
    image = serializers.ImageField(required=False, allow_null=True)
    image_url = serializers.CharField(
        max_length=4096,
        required=False,
        allow_null=True,
        write_only=True,
        help_text="URL to download image from (alternative to file upload)"
    )
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = RecipeImage
        fields = ['id', 'image', 'image_url', 'order', 'created_at', 'created_by']
        read_only_fields = ['id', 'created_at', 'created_by']

    def validate_image(self, value):
        """Validate image file type."""
        if value and not is_file_type_allowed(value.name, image_only=True):
            raise serializers.ValidationError(
                'Invalid file type. Allowed: .png, .jpg, .jpeg, .gif, .webp'
            )
        return value

    def validate(self, attrs):
        """Validate max images per recipe and require image source."""
        recipe = self.context.get('recipe')

        # Only validate on create, not update
        if self.instance is None:
            # Check max limit
            if recipe:
                current_count = RecipeImage.objects.filter(recipe=recipe).count()
                if current_count >= 10:
                    raise serializers.ValidationError(
                        'Maximum 10 images per recipe allowed. Delete an image first.'
                    )

            # Require either image file or URL
            if not attrs.get('image') and not attrs.get('image_url'):
                raise serializers.ValidationError(
                    'Either image file or image_url is required.'
                )

        return attrs
```

### Step 4: Add import for RecipeImage

At top of `cookbook/serializer.py`, ensure RecipeImage is imported:

```python
from cookbook.models import RecipeImage  # Add this if not present
```

### Verification
```bash
python manage.py shell -c "from cookbook.serializer import RecipeImageSerializer, RecipePrimaryImageSerializer; print('OK')"
```

---

## Task 5: ViewSet - Complete Code

Add this to `cookbook/views/api.py`. Add imports at top of file first:

### Imports to add at top of api.py:

```python
# Add these imports if not already present:
import io
import uuid
import mimetypes
import requests
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile
from rest_framework.exceptions import ValidationError
from PIL import UnidentifiedImageError
from requests.exceptions import MissingSchema

from cookbook.models import RecipeImage
from cookbook.serializer import RecipeImageSerializer
from cookbook.helper.image_processing import handle_image
from cookbook.helper.recipe_url_import import validate_import_url
```

### Complete ViewSet class:

```python
class RecipeImageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing multiple images per recipe.

    Endpoints:
    - GET    /api/recipe/{recipe_pk}/images/         - List all images
    - POST   /api/recipe/{recipe_pk}/images/         - Add new image
    - GET    /api/recipe/{recipe_pk}/images/{pk}/    - Get single image
    - PATCH  /api/recipe/{recipe_pk}/images/{pk}/    - Update (reorder)
    - DELETE /api/recipe/{recipe_pk}/images/{pk}/    - Delete image
    - POST   /api/recipe/{recipe_pk}/images/reorder/ - Bulk reorder
    """
    serializer_class = RecipeImageSerializer
    parser_classes = [MultiPartParser]
    permission_classes = [CustomIsUser]

    MAX_IMAGES_PER_RECIPE = 10

    def get_queryset(self):
        """Get images for the specified recipe in the current space."""
        recipe_pk = self.kwargs.get('recipe_pk')
        return RecipeImage.objects.filter(
            recipe_id=recipe_pk,
            space=self.request.space
        ).order_by('order', 'created_at')

    def get_recipe(self):
        """Get recipe and verify user has permission to access it."""
        recipe_pk = self.kwargs.get('recipe_pk')
        recipe = get_object_or_404(Recipe, pk=recipe_pk)

        if recipe.get_space() != self.request.space:
            raise PermissionDenied(
                detail='You do not have permission to access this recipe',
                code=403
            )
        return recipe

    def get_serializer_context(self):
        """Add recipe to serializer context for validation."""
        context = super().get_serializer_context()
        if 'recipe_pk' in self.kwargs:
            try:
                context['recipe'] = self.get_recipe()
            except Exception:
                pass
        return context

    def list(self, request, *args, **kwargs):
        """List all images for a recipe."""
        self.get_recipe()  # Verify access permission
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Get a single image."""
        self.get_recipe()  # Verify access permission
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        Add a new image to a recipe.

        Accepts either:
        - 'image': File upload (multipart form data)
        - 'image_url': URL to download image from

        The image will be processed (compressed, metadata stripped) before saving.
        """
        recipe = self.get_recipe()

        # Check max images limit
        current_count = RecipeImage.objects.filter(recipe=recipe).count()
        if current_count >= self.MAX_IMAGES_PER_RECIPE:
            raise ValidationError({
                'detail': f'Maximum {self.MAX_IMAGES_PER_RECIPE} images per recipe allowed. '
                          f'Delete an image before adding more.'
            })

        # Determine next order value
        max_order = RecipeImage.objects.filter(recipe=recipe).aggregate(
            Max('order')
        )['order__max']
        next_order = (max_order or -1) + 1

        # Process image from file or URL
        image_file = None
        filetype = '.jpeg'  # Default fallback

        if 'image' in request.FILES:
            # Handle direct file upload
            uploaded_file = request.FILES['image']
            image_file = uploaded_file
            filetype = mimetypes.guess_extension(
                uploaded_file.content_type
            ) or filetype

        elif 'image_url' in request.data and request.data['image_url']:
            # Handle URL-based image
            url = request.data['image_url']
            try:
                if validate_import_url(url):
                    response = requests.get(
                        url,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0"
                        },
                        timeout=10
                    )
                    response.raise_for_status()

                    image_file = ContentFile(response.content)
                    filetype = mimetypes.guess_extension(
                        response.headers.get('content-type', 'image/jpeg')
                    ) or filetype
            except UnidentifiedImageError as e:
                raise ValidationError({'image_url': f'Could not process image from URL: {e}'})
            except MissingSchema as e:
                raise ValidationError({'image_url': f'Invalid URL format: {e}'})
            except requests.RequestException as e:
                raise ValidationError({'image_url': f'Failed to download image: {e}'})
        else:
            raise ValidationError({'detail': 'Either image file or image_url is required'})

        if image_file is None:
            raise ValidationError({'detail': 'Could not process the provided image'})

        # Process image (compress, strip metadata) using existing helper
        try:
            processed_image = handle_image(request, image_file, filetype)
        except Exception as e:
            raise ValidationError({'detail': f'Image processing failed: {e}'})

        # Create the RecipeImage instance
        recipe_image = RecipeImage(
            recipe=recipe,
            order=next_order,
            created_by=request.user,
            space=recipe.space,
        )

        # Save with UUID filename to avoid collisions
        filename = f'{uuid.uuid4()}_{recipe.pk}{filetype}'
        recipe_image.image.save(filename, processed_image)
        recipe_image.save()

        serializer = self.get_serializer(recipe_image)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        """Update image (primarily for reordering via 'order' field)."""
        self.get_recipe()  # Verify access permission
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete a recipe image and its file."""
        self.get_recipe()  # Verify access permission
        instance = self.get_object()

        # Delete the actual image file from storage
        if instance.image:
            instance.image.delete(save=False)

        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @decorators.action(detail=False, methods=['POST'])
    def reorder(self, request, recipe_pk=None):
        """
        Bulk reorder images.

        Request body:
        {
            "image_ids": [3, 1, 2]  // New order - first ID becomes order 0
        }
        """
        recipe = self.get_recipe()
        image_ids = request.data.get('image_ids', [])

        # Validate input
        if not isinstance(image_ids, list):
            return Response(
                {'error': 'image_ids must be a list of integers'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(image_ids) == 0:
            return Response(
                {'error': 'image_ids cannot be empty'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check for duplicates
        if len(image_ids) != len(set(image_ids)):
            return Response(
                {'error': 'Duplicate image IDs are not allowed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate all IDs belong to this recipe
        existing_images = RecipeImage.objects.filter(
            recipe=recipe,
            id__in=image_ids
        )

        if existing_images.count() != len(image_ids):
            return Response(
                {'error': 'One or more image IDs are invalid or do not belong to this recipe'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update order for each image
        updated_images = []
        for new_order, image_id in enumerate(image_ids):
            RecipeImage.objects.filter(id=image_id).update(order=new_order)
            updated_images.append({'id': image_id, 'order': new_order})

        return Response({
            'status': 'success',
            'images': updated_images
        }, status=status.HTTP_200_OK)
```

### Verification
```bash
python manage.py shell -c "from cookbook.views.api import RecipeImageViewSet; print('OK')"
```

---

## Task 6: URL Routes - Complete Code

Add these URL patterns to `cookbook/urls.py`.

**Note:** This project does NOT use drf-nested-routers. Use manual URL patterns.

Find the `urlpatterns` list and add these entries:

```python
# Add these imports at top if not present:
from cookbook.views import api

# Add these URL patterns to urlpatterns list:
urlpatterns = [
    # ... existing patterns ...

    # Recipe Images API - nested under recipe
    path(
        'api/recipe/<int:recipe_pk>/images/',
        api.RecipeImageViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }),
        name='recipe-images-list'
    ),
    path(
        'api/recipe/<int:recipe_pk>/images/<int:pk>/',
        api.RecipeImageViewSet.as_view({
            'get': 'retrieve',
            'patch': 'partial_update',
            'delete': 'destroy'
        }),
        name='recipe-images-detail'
    ),
    path(
        'api/recipe/<int:recipe_pk>/images/reorder/',
        api.RecipeImageViewSet.as_view({
            'post': 'reorder'
        }),
        name='recipe-images-reorder'
    ),
]
```

### Verification
```bash
# Start the server and test:
python manage.py runserver

# In another terminal, test the endpoint (replace 1 with valid recipe ID):
curl http://localhost:8000/api/recipe/1/images/
# Should return [] or list of images (or 403 if not authenticated)
```

---

## Task 7: Django Admin - Complete Code

Add to `cookbook/admin.py`:

```python
from cookbook.models import RecipeImage  # Add to imports


@admin.register(RecipeImage)
class RecipeImageAdmin(admin.ModelAdmin):
    """Admin configuration for RecipeImage model."""
    list_display = ('id', 'recipe', 'order', 'created_at', 'created_by', 'space')
    list_filter = ('space', 'created_by', 'created_at')
    search_fields = ('recipe__name',)
    readonly_fields = ('created_at', 'created_by', 'space')
    ordering = ('recipe', 'order')
    raw_id_fields = ('recipe', 'created_by')

    def get_queryset(self, request):
        """Optimize query with select_related."""
        return super().get_queryset(request).select_related(
            'recipe', 'created_by', 'space'
        )
```

### Verification
```bash
python manage.py runserver
# Go to http://localhost:8000/admin/cookbook/recipeimage/
# Should see RecipeImage admin page
```

---

## Task 8: RecipeImageManager.vue - Complete Component

Create file: `vue3/src/components/inputs/RecipeImageManager.vue`

```vue
<template>
    <v-card variant="outlined" :loading="loading" :disabled="disabled">
        <v-card-title class="d-flex align-center">
            <v-icon icon="fa-solid fa-images" class="mr-2"></v-icon>
            <span>{{ $t('Images') }}</span>
            <v-spacer></v-spacer>
            <v-chip size="small" :color="images.length >= maxImages ? 'warning' : 'default'">
                {{ images.length }}/{{ maxImages }}
            </v-chip>
        </v-card-title>

        <v-card-text>
            <!-- Empty state -->
            <v-alert
                v-if="images.length === 0 && !loading"
                type="info"
                variant="tonal"
                class="mb-4"
            >
                {{ $t('No additional images yet. Upload images below.') }}
            </v-alert>

            <!-- Draggable image grid -->
            <vue-draggable
                v-if="images.length > 0"
                v-model="localImages"
                handle=".drag-handle"
                item-key="id"
                class="d-flex flex-wrap ga-3 mb-4"
                @end="onReorder"
            >
                <template #item="{ element: img, index }">
                    <div class="recipe-image-item position-relative">
                        <v-img
                            :src="img.image"
                            width="140"
                            height="140"
                            cover
                            class="rounded-lg"
                        >
                            <div class="image-overlay d-flex flex-column align-center justify-center h-100">
                                <v-btn
                                    icon
                                    size="small"
                                    color="error"
                                    variant="flat"
                                    class="mb-1"
                                    :loading="deletingId === img.id"
                                    @click="deleteImage(img.id)"
                                >
                                    <v-icon icon="fa-solid fa-trash"></v-icon>
                                </v-btn>
                                <v-icon
                                    class="drag-handle cursor-move"
                                    icon="fa-solid fa-grip-vertical"
                                    color="white"
                                ></v-icon>
                            </div>
                        </v-img>
                        <v-chip
                            size="x-small"
                            class="position-absolute order-chip"
                            color="primary"
                        >
                            {{ index + 1 }}
                        </v-chip>
                    </div>
                </template>
            </vue-draggable>

            <!-- Add image section -->
            <v-divider v-if="images.length > 0" class="mb-4"></v-divider>

            <template v-if="images.length < maxImages">
                <v-file-upload
                    v-model="newFile"
                    :title="$t('Add_Image')"
                    :browse-text="$t('Select_File')"
                    :divider-text="$t('or')"
                    :disabled="loading || uploading"
                    accept="image/png,image/jpeg,image/gif,image/webp"
                    density="compact"
                    @update:model-value="onFileSelected"
                />

                <div v-if="uploading" class="d-flex align-center mt-2">
                    <v-progress-circular indeterminate size="20" class="mr-2"></v-progress-circular>
                    <span class="text-caption">{{ $t('Uploading...') }}</span>
                </div>
            </template>

            <v-alert v-else type="warning" variant="tonal">
                {{ $t('Maximum images reached') }} ({{ images.length }}/{{ maxImages }})
            </v-alert>
        </v-card-text>
    </v-card>
</template>

<script setup lang="ts">
import { ref, computed, watch, type PropType } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { VFileUpload } from 'vuetify/labs/VFileUpload'
import { useFileApi } from '@/composables/useFileApi'
import { useMessageStore, ErrorMessageType } from '@/stores/MessageStore'

// Type definition for RecipeImage
interface RecipeImage {
    id: number
    image: string
    order: number
    createdAt?: Date
    createdBy?: { id: number; displayName: string }
}

// Props
const props = defineProps({
    modelValue: {
        type: Array as PropType<RecipeImage[]>,
        required: true,
        default: () => []
    },
    recipeId: {
        type: Number,
        required: false,
        default: undefined
    },
    maxImages: {
        type: Number,
        default: 10
    },
    disabled: {
        type: Boolean,
        default: false
    }
})

// Emits
const emit = defineEmits<{
    (e: 'update:modelValue', value: RecipeImage[]): void
}>()

// Composables
const { addRecipeImage, deleteRecipeImage, reorderRecipeImages } = useFileApi()
const messageStore = useMessageStore()

// Reactive state
const loading = ref(false)
const uploading = ref(false)
const deletingId = ref<number | null>(null)
const newFile = ref<File | null>(null)
const localImages = ref<RecipeImage[]>([])

// Computed
const images = computed(() => props.modelValue)

// Watch for external changes to sync local state
watch(
    () => props.modelValue,
    (newVal) => {
        localImages.value = [...newVal].sort((a, b) => a.order - b.order)
    },
    { immediate: true, deep: true }
)

/**
 * Handle file selection - upload immediately
 */
async function onFileSelected(file: File | null) {
    if (!file || !props.recipeId) {
        return
    }

    uploading.value = true
    try {
        const newImage = await addRecipeImage(props.recipeId, file)
        const updated = [...props.modelValue, newImage]
        emit('update:modelValue', updated)
        newFile.value = null // Clear the input
    } catch (error) {
        messageStore.addError(ErrorMessageType.CREATE_ERROR, error)
    } finally {
        uploading.value = false
    }
}

/**
 * Delete an image
 */
async function deleteImage(imageId: number) {
    if (!props.recipeId) {
        return
    }

    deletingId.value = imageId
    try {
        await deleteRecipeImage(props.recipeId, imageId)
        const updated = props.modelValue.filter(img => img.id !== imageId)
        emit('update:modelValue', updated)
    } catch (error) {
        messageStore.addError(ErrorMessageType.DELETE_ERROR, error)
    } finally {
        deletingId.value = null
    }
}

/**
 * Handle drag-and-drop reorder completion
 */
async function onReorder() {
    if (!props.recipeId || localImages.value.length === 0) {
        return
    }

    const imageIds = localImages.value.map(img => img.id)

    loading.value = true
    try {
        await reorderRecipeImages(props.recipeId, imageIds)
        // Update order values in emitted data
        const updated = localImages.value.map((img, idx) => ({
            ...img,
            order: idx
        }))
        emit('update:modelValue', updated)
    } catch (error) {
        messageStore.addError(ErrorMessageType.UPDATE_ERROR, error)
        // Revert to original order on error
        localImages.value = [...props.modelValue].sort((a, b) => a.order - b.order)
    } finally {
        loading.value = false
    }
}
</script>

<style scoped>
.recipe-image-item {
    transition: transform 0.2s ease;
}

.recipe-image-item:hover {
    transform: scale(1.02);
}

.image-overlay {
    background: rgba(0, 0, 0, 0.5);
    opacity: 0;
    transition: opacity 0.2s ease;
}

.recipe-image-item:hover .image-overlay {
    opacity: 1;
}

.order-chip {
    top: 4px;
    left: 4px;
}

.drag-handle {
    cursor: move;
}

.cursor-move {
    cursor: move;
}
</style>
```

---

## Task 9: RecipeImageGallery.vue - Complete Component

Create file: `vue3/src/components/display/RecipeImageGallery.vue`

```vue
<template>
    <!-- Only show if there's more than 1 image total -->
    <v-card v-if="allImages.length > 1" class="mt-2" variant="outlined">
        <v-card-title class="text-body-1 d-flex align-center">
            <v-icon icon="fa-solid fa-images" class="mr-2" size="small"></v-icon>
            {{ $t('Images') }} ({{ allImages.length }})
        </v-card-title>

        <v-card-text class="pt-0">
            <!-- Thumbnail strip -->
            <div class="thumbnail-strip d-flex overflow-x-auto ga-2 pb-2">
                <v-img
                    v-for="(imgUrl, index) in allImages"
                    :key="index"
                    :src="imgUrl"
                    width="80"
                    height="80"
                    cover
                    class="rounded cursor-pointer flex-shrink-0 thumbnail"
                    :class="{ 'thumbnail-active': lightboxOpen && selectedIndex === index }"
                    @click="openLightbox(index)"
                />
            </div>
        </v-card-text>
    </v-card>

    <!-- Lightbox dialog -->
    <v-dialog v-model="lightboxOpen" max-width="95vw" max-height="95vh">
        <v-card class="bg-black">
            <!-- Toolbar -->
            <v-toolbar density="compact" color="transparent" class="text-white">
                <v-toolbar-title class="text-body-2">
                    {{ selectedIndex + 1 }} / {{ allImages.length }}
                </v-toolbar-title>
                <v-spacer></v-spacer>
                <v-btn icon variant="text" @click="lightboxOpen = false">
                    <v-icon icon="fa-solid fa-xmark"></v-icon>
                </v-btn>
            </v-toolbar>

            <!-- Main image area with navigation -->
            <div
                class="d-flex align-center justify-center position-relative"
                style="min-height: 60vh;"
            >
                <!-- Previous button -->
                <v-btn
                    icon
                    variant="text"
                    size="large"
                    class="position-absolute nav-btn nav-prev text-white"
                    :disabled="selectedIndex === 0"
                    @click="prev"
                >
                    <v-icon icon="fa-solid fa-chevron-left" size="x-large"></v-icon>
                </v-btn>

                <!-- Main image -->
                <v-img
                    :src="allImages[selectedIndex]"
                    max-height="75vh"
                    max-width="85vw"
                    contain
                    class="mx-auto"
                />

                <!-- Next button -->
                <v-btn
                    icon
                    variant="text"
                    size="large"
                    class="position-absolute nav-btn nav-next text-white"
                    :disabled="selectedIndex === allImages.length - 1"
                    @click="next"
                >
                    <v-icon icon="fa-solid fa-chevron-right" size="x-large"></v-icon>
                </v-btn>
            </div>

            <!-- Thumbnail strip in lightbox -->
            <div class="d-flex justify-center overflow-x-auto ga-1 pa-2 bg-grey-darken-4">
                <v-img
                    v-for="(imgUrl, index) in allImages"
                    :key="'lb-' + index"
                    :src="imgUrl"
                    width="50"
                    height="50"
                    cover
                    class="rounded cursor-pointer flex-shrink-0 lightbox-thumb"
                    :class="{ 'lightbox-thumb-active': selectedIndex === index }"
                    @click="selectedIndex = index"
                />
            </div>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, type PropType } from 'vue'

// Type for recipe images from API
interface RecipeImage {
    id: number
    image: string
    order: number
}

// Props
const props = defineProps({
    images: {
        type: Array as PropType<RecipeImage[]>,
        required: true,
        default: () => []
    },
    primaryImage: {
        type: String as PropType<string | null>,
        required: false,
        default: null
    }
})

// Reactive state
const lightboxOpen = ref(false)
const selectedIndex = ref(0)

/**
 * Combine primary image with additional images, avoiding duplicates
 */
const allImages = computed(() => {
    const urls: string[] = []

    // Add primary image first if it exists
    if (props.primaryImage) {
        urls.push(props.primaryImage)
    }

    // Add additional images, sorted by order
    const sortedImages = [...props.images].sort((a, b) => a.order - b.order)

    for (const img of sortedImages) {
        // Avoid duplicate if primary is also in the images array
        if (img.image && img.image !== props.primaryImage) {
            urls.push(img.image)
        }
    }

    return urls
})

/**
 * Open lightbox at specific image index
 */
function openLightbox(index: number) {
    selectedIndex.value = index
    lightboxOpen.value = true
}

/**
 * Navigate to previous image
 */
function prev() {
    if (selectedIndex.value > 0) {
        selectedIndex.value--
    }
}

/**
 * Navigate to next image
 */
function next() {
    if (selectedIndex.value < allImages.value.length - 1) {
        selectedIndex.value++
    }
}

/**
 * Handle keyboard navigation
 */
function handleKeydown(e: KeyboardEvent) {
    if (!lightboxOpen.value) return

    switch (e.key) {
        case 'ArrowLeft':
            e.preventDefault()
            prev()
            break
        case 'ArrowRight':
            e.preventDefault()
            next()
            break
        case 'Escape':
            e.preventDefault()
            lightboxOpen.value = false
            break
    }
}

// Lifecycle - keyboard listener
onMounted(() => {
    window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.thumbnail-strip {
    scrollbar-width: thin;
    scrollbar-color: rgba(0, 0, 0, 0.3) transparent;
}

.thumbnail {
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    border: 2px solid transparent;
}

.thumbnail:hover {
    transform: scale(1.05);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.thumbnail-active {
    border-color: rgb(var(--v-theme-primary));
}

.cursor-pointer {
    cursor: pointer;
}

.nav-btn {
    z-index: 1;
}

.nav-prev {
    left: 16px;
}

.nav-next {
    right: 16px;
}

.lightbox-thumb {
    opacity: 0.6;
    transition: opacity 0.2s ease;
    border: 2px solid transparent;
}

.lightbox-thumb:hover {
    opacity: 0.9;
}

.lightbox-thumb-active {
    opacity: 1;
    border-color: rgb(var(--v-theme-primary));
}
</style>
```

---

## Task 10: useFileApi.ts - Functions to Add

Add these functions to `vue3/src/composables/useFileApi.ts`:

```typescript
// Add this interface near the top of the file
interface RecipeImage {
    id: number
    image: string
    order: number
    createdAt?: Date
    createdBy?: { id: number; displayName: string }
}

// Add these functions inside the useFileApi() function, before the return statement:

/**
 * Get all images for a recipe
 * @param recipeId ID of the recipe
 * @returns Promise resolving to array of RecipeImage objects
 */
function getRecipeImages(recipeId: number): Promise<RecipeImage[]> {
    return fetch(getDjangoUrl(`api/recipe/${recipeId}/images/`), {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
        },
    }).then(r => {
        if (!r.ok) throw new ResponseError(r)
        return r.json()
    })
}

/**
 * Add a new image to a recipe
 * @param recipeId ID of the recipe
 * @param file File object to upload, or null if using imageUrl
 * @param imageUrl Optional URL to download image from
 * @returns Promise resolving to the created RecipeImage
 */
function addRecipeImage(
    recipeId: number,
    file: File | null,
    imageUrl?: string
): Promise<RecipeImage> {
    const formData = new FormData()

    if (file != null) {
        formData.append('image', file)
    }
    if (imageUrl) {
        formData.append('image_url', imageUrl)
    }

    fileApiLoading.value = true

    return fetch(getDjangoUrl(`api/recipe/${recipeId}/images/`), {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
        },
        body: formData
    }).then(r => {
        if (!r.ok) throw new ResponseError(r)
        return r.json()
    }).finally(() => {
        fileApiLoading.value = false
    })
}

/**
 * Delete a recipe image
 * @param recipeId ID of the recipe
 * @param imageId ID of the image to delete
 */
function deleteRecipeImage(recipeId: number, imageId: number): Promise<void> {
    fileApiLoading.value = true

    return fetch(getDjangoUrl(`api/recipe/${recipeId}/images/${imageId}/`), {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
        },
    }).then(r => {
        if (!r.ok) throw new ResponseError(r)
    }).finally(() => {
        fileApiLoading.value = false
    })
}

/**
 * Reorder recipe images
 * @param recipeId ID of the recipe
 * @param imageIds Array of image IDs in the new order
 */
function reorderRecipeImages(recipeId: number, imageIds: number[]): Promise<void> {
    fileApiLoading.value = true

    return fetch(getDjangoUrl(`api/recipe/${recipeId}/images/reorder/`), {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ image_ids: imageIds })
    }).then(r => {
        if (!r.ok) throw new ResponseError(r)
    }).finally(() => {
        fileApiLoading.value = false
    })
}

// Update the return statement to include new functions:
return {
    fileApiLoading,
    createOrUpdateUserFile,
    updateRecipeImage,
    doAiImport,
    doAppImport,
    // Add these:
    getRecipeImages,
    addRecipeImage,
    deleteRecipeImage,
    reorderRecipeImages,
}
```

---

## Task 15: Backend Tests - Complete Implementation

Create file: `cookbook/tests/api/test_recipe_images.py`

```python
"""
Tests for RecipeImage API endpoints.

Run with: pytest cookbook/tests/api/test_recipe_images.py -v
"""
import io
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django_scopes import scopes_disabled

from cookbook.models import Recipe, RecipeImage
from cookbook.tests.factories import RecipeFactory, SpaceFactory, UserFactory


def create_test_image(name='test.jpg', size=(100, 100), color='red', format='JPEG'):
    """Create a test image file for upload testing."""
    image = Image.new('RGB', size, color=color)
    file = io.BytesIO()
    image.save(file, format)
    file.seek(0)
    return SimpleUploadedFile(
        name=name,
        content=file.read(),
        content_type=f'image/{format.lower()}'
    )


@pytest.fixture
def space(db):
    """Create a test space."""
    with scopes_disabled():
        return SpaceFactory()


@pytest.fixture
def user(db, space):
    """Create a test user in the space."""
    with scopes_disabled():
        return UserFactory(space=space, groups='user')


@pytest.fixture
def recipe(db, user, space):
    """Create a test recipe."""
    with scopes_disabled():
        return RecipeFactory(
            created_by=user,
            space=space,
            steps__count=0,
            keywords__count=0
        )


@pytest.fixture
def recipe_image(db, recipe, user):
    """Create a test recipe image."""
    with scopes_disabled():
        image_file = create_test_image('fixture.jpg')
        return RecipeImage.objects.create(
            recipe=recipe,
            image=image_file,
            order=0,
            created_by=user,
            space=recipe.space
        )


@pytest.fixture
def authenticated_client(db, client, user, space):
    """Return an authenticated test client."""
    client.force_login(user)
    # Set space in session (adjust based on how your middleware works)
    session = client.session
    session['space_id'] = space.id
    session.save()
    return client


@pytest.mark.django_db
class TestRecipeImageModel:
    """Tests for the RecipeImage model."""

    def test_create_recipe_image(self, recipe, user):
        """Test creating a recipe image."""
        with scopes_disabled():
            image_file = create_test_image()
            recipe_image = RecipeImage.objects.create(
                recipe=recipe,
                image=image_file,
                order=0,
                created_by=user,
                space=recipe.space
            )

            assert recipe_image.id is not None
            assert recipe_image.recipe == recipe
            assert recipe_image.order == 0
            assert recipe_image.space == recipe.space
            assert recipe_image.created_by == user
            assert recipe_image.image is not None

    def test_recipe_image_ordering(self, recipe, user):
        """Test that images are ordered by order field."""
        with scopes_disabled():
            # Create images out of order
            for order in [2, 0, 1]:
                RecipeImage.objects.create(
                    recipe=recipe,
                    image=create_test_image(f'test{order}.jpg'),
                    order=order,
                    created_by=user,
                    space=recipe.space
                )

            images = list(RecipeImage.objects.filter(recipe=recipe))
            orders = [img.order for img in images]
            assert orders == [0, 1, 2], "Images should be ordered by order field"

    def test_cascade_delete_with_recipe(self, recipe, user):
        """Test that images are deleted when recipe is deleted."""
        with scopes_disabled():
            RecipeImage.objects.create(
                recipe=recipe,
                image=create_test_image(),
                order=0,
                created_by=user,
                space=recipe.space
            )

            recipe_id = recipe.id
            assert RecipeImage.objects.filter(recipe_id=recipe_id).count() == 1

            recipe.delete()

            assert RecipeImage.objects.filter(recipe_id=recipe_id).count() == 0

    def test_get_space_method(self, recipe_image):
        """Test get_space returns recipe's space."""
        assert recipe_image.get_space() == recipe_image.recipe.space

    def test_str_representation(self, recipe_image):
        """Test string representation of RecipeImage."""
        expected = f"Image {recipe_image.order} for {recipe_image.recipe.name}"
        assert str(recipe_image) == expected


@pytest.mark.django_db
class TestRecipeImageAPI:
    """Tests for the RecipeImage API endpoints."""

    def test_list_images_empty(self, authenticated_client, recipe):
        """Test listing images for a recipe with no images."""
        response = authenticated_client.get(f'/api/recipe/{recipe.id}/images/')

        assert response.status_code == 200
        assert response.json() == []

    def test_list_images(self, authenticated_client, recipe, user):
        """Test listing images for a recipe."""
        with scopes_disabled():
            for i in range(3):
                RecipeImage.objects.create(
                    recipe=recipe,
                    image=create_test_image(f'test{i}.jpg'),
                    order=i,
                    created_by=user,
                    space=recipe.space
                )

        response = authenticated_client.get(f'/api/recipe/{recipe.id}/images/')

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # Verify ordering
        assert data[0]['order'] == 0
        assert data[1]['order'] == 1
        assert data[2]['order'] == 2

    def test_add_image(self, authenticated_client, recipe):
        """Test adding an image to a recipe."""
        image = create_test_image('upload.jpg')

        response = authenticated_client.post(
            f'/api/recipe/{recipe.id}/images/',
            {'image': image},
            format='multipart'
        )

        assert response.status_code == 201
        data = response.json()
        assert 'id' in data
        assert data['order'] == 0
        assert 'image' in data

        with scopes_disabled():
            assert RecipeImage.objects.filter(recipe=recipe).count() == 1

    def test_add_image_auto_increments_order(self, authenticated_client, recipe, user):
        """Test that new images get incrementing order values."""
        with scopes_disabled():
            RecipeImage.objects.create(
                recipe=recipe,
                image=create_test_image('first.jpg'),
                order=0,
                created_by=user,
                space=recipe.space
            )

        response = authenticated_client.post(
            f'/api/recipe/{recipe.id}/images/',
            {'image': create_test_image('second.jpg')},
            format='multipart'
        )

        assert response.status_code == 201
        assert response.json()['order'] == 1

    def test_add_image_max_limit(self, authenticated_client, recipe, user):
        """Test that 10 image limit is enforced."""
        with scopes_disabled():
            # Create 10 images
            for i in range(10):
                RecipeImage.objects.create(
                    recipe=recipe,
                    image=create_test_image(f'test{i}.jpg'),
                    order=i,
                    created_by=user,
                    space=recipe.space
                )

        # Try to add 11th
        response = authenticated_client.post(
            f'/api/recipe/{recipe.id}/images/',
            {'image': create_test_image('extra.jpg')},
            format='multipart'
        )

        assert response.status_code == 400
        # Check error message mentions the limit
        response_text = str(response.json()).lower()
        assert 'maximum' in response_text or '10' in response_text

    def test_delete_image(self, authenticated_client, recipe_image):
        """Test deleting a recipe image."""
        image_id = recipe_image.id
        recipe_id = recipe_image.recipe.id

        response = authenticated_client.delete(
            f'/api/recipe/{recipe_id}/images/{image_id}/'
        )

        assert response.status_code == 204

        with scopes_disabled():
            assert not RecipeImage.objects.filter(id=image_id).exists()

    def test_reorder_images(self, authenticated_client, recipe, user):
        """Test reordering recipe images."""
        with scopes_disabled():
            images = []
            for i in range(3):
                img = RecipeImage.objects.create(
                    recipe=recipe,
                    image=create_test_image(f'test{i}.jpg'),
                    order=i,
                    created_by=user,
                    space=recipe.space
                )
                images.append(img)

        # Reverse the order
        new_order = [images[2].id, images[1].id, images[0].id]

        response = authenticated_client.post(
            f'/api/recipe/{recipe.id}/images/reorder/',
            {'image_ids': new_order},
            content_type='application/json'
        )

        assert response.status_code == 200
        assert response.json()['status'] == 'success'

        # Verify new order in database
        with scopes_disabled():
            for idx, img_id in enumerate(new_order):
                img = RecipeImage.objects.get(id=img_id)
                assert img.order == idx

    def test_reorder_invalid_ids(self, authenticated_client, recipe):
        """Test reorder with invalid image IDs."""
        response = authenticated_client.post(
            f'/api/recipe/{recipe.id}/images/reorder/',
            {'image_ids': [99999, 99998]},
            content_type='application/json'
        )

        assert response.status_code == 400
        assert 'error' in response.json()

    def test_reorder_duplicate_ids(self, authenticated_client, recipe, recipe_image):
        """Test reorder rejects duplicate IDs."""
        response = authenticated_client.post(
            f'/api/recipe/{recipe.id}/images/reorder/',
            {'image_ids': [recipe_image.id, recipe_image.id]},
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_invalid_file_type_rejected(self, authenticated_client, recipe):
        """Test that non-image files are rejected."""
        fake_file = SimpleUploadedFile(
            name='test.txt',
            content=b'not an image',
            content_type='text/plain'
        )

        response = authenticated_client.post(
            f'/api/recipe/{recipe.id}/images/',
            {'image': fake_file},
            format='multipart'
        )

        assert response.status_code == 400

    def test_permission_denied_other_space(self, client, recipe, space):
        """Test that users cannot access images from another space."""
        with scopes_disabled():
            # Create user in different space
            other_space = SpaceFactory()
            other_user = UserFactory(space=other_space, groups='user')

        client.force_login(other_user)

        response = client.get(f'/api/recipe/{recipe.id}/images/')

        assert response.status_code == 403

    def test_recipe_not_found(self, authenticated_client):
        """Test 404 for non-existent recipe."""
        response = authenticated_client.get('/api/recipe/99999/images/')

        assert response.status_code == 404
```

---

## Appendix D: Troubleshooting

### Common Errors and Solutions

#### 1. "No module named 'cookbook.models.RecipeImage'"
**Cause:** Model not defined or migration not applied
**Solution:**
```bash
# Check model is in models.py
grep "class RecipeImage" cookbook/models.py

# Run migrations
python manage.py makemigrations cookbook
python manage.py migrate
```

#### 2. "relation 'cookbook_recipeimage' does not exist"
**Cause:** Database migration not applied
**Solution:**
```bash
python manage.py migrate cookbook
```

#### 3. "ScopedManager requires space parameter"
**Cause:** Query executed outside of scope context
**Solution:** Ensure middleware sets `request.space` or use `scopes_disabled()` context manager in tests

#### 4. "Permission denied" (403) on image upload
**Cause:** User doesn't have access to recipe's space
**Solution:** Verify user belongs to the space via UserSpace model:
```python
UserSpace.objects.filter(user=user, space=recipe.space).exists()
```

#### 5. Frontend: "Cannot read property 'images' of undefined"
**Cause:** Recipe object doesn't have images array yet
**Solution:** Check RecipeSerializer includes `images` field and API returns it

#### 6. Images not displaying after upload
**Cause:** MEDIA_URL not configured correctly
**Solution:** Check `settings.py`:
```python
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'mediafiles')
```

#### 7. "Maximum 10 images" error when less than 10 exist
**Cause:** Orphaned images or counting query issue
**Solution:** Check the count query filters by recipe:
```python
RecipeImage.objects.filter(recipe=recipe).count()
```

#### 8. Drag-and-drop not working in RecipeImageManager
**Cause:** vue-draggable-plus not installed or imported wrong
**Solution:**
```bash
cd vue3
npm install vue-draggable-plus
```
Verify import: `import { VueDraggable } from 'vue-draggable-plus'`

#### 9. TypeScript errors about RecipeImage type
**Cause:** Types not defined or OpenAPI not regenerated
**Solution:** Either regenerate OpenAPI types or add manual type in `vue3/src/types/`

#### 10. Tests failing with "space_1 fixture not found"
**Cause:** Using wrong fixture names
**Solution:** This codebase uses `space` not `space_1`. Check conftest.py for available fixtures.

---

## Quick Reference: File Locations

| What | Where |
|------|-------|
| Django models | `cookbook/models.py` |
| Serializers | `cookbook/serializer.py` |
| API views | `cookbook/views/api.py` |
| URL routes | `cookbook/urls.py` |
| Django admin | `cookbook/admin.py` |
| Test factories | `cookbook/tests/factories/__init__.py` |
| Test fixtures | `cookbook/tests/conftest.py` |
| Vue components | `vue3/src/components/` |
| Vue composables | `vue3/src/composables/` |
| Translations | `vue3/src/locales/en.json` |
