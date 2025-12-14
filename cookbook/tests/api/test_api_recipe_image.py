"""
Tests for RecipeImage API endpoints (/api/recipe-image/).

Tests cover:
- CRUD operations (list, create, retrieve, update, delete)
- Permission checks: anonymous (403), guest (read-only), user/admin (full)
- Space isolation (multi-tenant)
- Custom actions: set_primary, reorder
- Model behavior: auto-primary on first image, ordering by sort_order

Related files:
- Model: cookbook/models.py (RecipeImage)
- ViewSet: cookbook/views/api.py (RecipeImageViewSet)
- Serializer: cookbook/serializer.py (RecipeImageItemSerializer)
"""

import io
import json
import pytest
from PIL import Image
from django.contrib import auth
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django_scopes import scopes_disabled

from cookbook.models import Recipe, RecipeImage

LIST_URL = 'api:recipeimage-list'
DETAIL_URL = 'api:recipeimage-detail'


def create_test_image():
    """Create a simple test image file."""
    file = io.BytesIO()
    image = Image.new('RGB', (100, 100), color='red')
    image.save(file, 'PNG')
    file.name = 'test.png'
    file.seek(0)
    return SimpleUploadedFile(
        name='test.png',
        content=file.read(),
        content_type='image/png'
    )


def get_recipe_image(recipe, user, **kwargs):
    """Create a RecipeImage for testing."""
    defaults = {
        'recipe': recipe,
        'created_by': user,
        'is_primary': kwargs.pop('is_primary', False),
        'sort_order': kwargs.pop('sort_order', 0),
    }
    defaults.update(kwargs)
    return RecipeImage.objects.create(**defaults)


# ==================== PERMISSION TESTS ====================

@pytest.mark.parametrize("arg", [
    ['a_u', 403],
    ['g1_s1', 200],
    ['u1_s1', 200],
    ['a1_s1', 200],
])
def test_list_permission(arg, request, recipe_1_s1):
    """Test list endpoint permissions."""
    c = request.getfixturevalue(arg[0])
    assert c.get(reverse(LIST_URL)).status_code == arg[1]


@pytest.mark.parametrize("arg", [
    ['a_u', 403],
    ['g1_s1', 403],
    ['u1_s1', 201],
    ['a1_s1', 201],
])
def test_create_permission(arg, request, recipe_1_s1):
    """Test create endpoint permissions."""
    c = request.getfixturevalue(arg[0])
    image_file = create_test_image()
    response = c.post(
        reverse(LIST_URL),
        {'recipe': recipe_1_s1.id, 'image': image_file},
        format='multipart'
    )
    assert response.status_code == arg[1]


@pytest.mark.parametrize("arg", [
    ['a_u', 403],
    ['g1_s1', 403],
    ['u1_s1', 200],
    ['a1_s1', 200],
])
def test_update_permission(arg, request, recipe_1_s1, u1_s1):
    """Test update endpoint permissions."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        recipe_image = get_recipe_image(recipe_1_s1, user)

    c = request.getfixturevalue(arg[0])
    response = c.patch(
        reverse(DETAIL_URL, args=[recipe_image.id]),
        {'sort_order': 5},
        content_type='application/json'
    )
    assert response.status_code == arg[1]


@pytest.mark.parametrize("arg", [
    ['a_u', 403],
    ['g1_s1', 403],
    ['u1_s1', 204],
    ['a1_s1', 204],
])
def test_delete_permission(arg, request, recipe_1_s1, u1_s1):
    """Test delete endpoint permissions."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        recipe_image = get_recipe_image(recipe_1_s1, user)

    c = request.getfixturevalue(arg[0])
    response = c.delete(reverse(DETAIL_URL, args=[recipe_image.id]))
    assert response.status_code == arg[1]


# ==================== SPACE ISOLATION TESTS ====================

def test_list_space(recipe_1_s1, u1_s1, u1_s2):
    """Test that users only see images from their space."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        get_recipe_image(recipe_1_s1, user)

    # User in space 1 sees the image
    response = u1_s1.get(reverse(LIST_URL))
    assert len(json.loads(response.content)['results']) == 1

    # User in space 2 does not see the image
    response = u1_s2.get(reverse(LIST_URL))
    assert len(json.loads(response.content)['results']) == 0


def test_detail_space(recipe_1_s1, u1_s1, u1_s2):
    """Test that users get 404 for images in other spaces."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        recipe_image = get_recipe_image(recipe_1_s1, user)

    # User in space 1 can access
    assert u1_s1.get(reverse(DETAIL_URL, args=[recipe_image.id])).status_code == 200

    # User in space 2 gets 404
    assert u1_s2.get(reverse(DETAIL_URL, args=[recipe_image.id])).status_code == 404


# ==================== CRUD TESTS ====================

def test_list_filter_by_recipe(recipe_1_s1, recipe_2_s1, u1_s1):
    """Test filtering images by recipe ID."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        get_recipe_image(recipe_1_s1, user)
        get_recipe_image(recipe_1_s1, user)
        get_recipe_image(recipe_2_s1, user)

    # Filter by recipe 1
    response = u1_s1.get(f"{reverse(LIST_URL)}?recipe={recipe_1_s1.id}")
    results = json.loads(response.content)['results']
    assert len(results) == 2

    # Filter by recipe 2
    response = u1_s1.get(f"{reverse(LIST_URL)}?recipe={recipe_2_s1.id}")
    results = json.loads(response.content)['results']
    assert len(results) == 1


def test_update_sort_order(recipe_1_s1, u1_s1):
    """Test updating image sort order."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        recipe_image = get_recipe_image(recipe_1_s1, user, sort_order=0)

    response = u1_s1.patch(
        reverse(DETAIL_URL, args=[recipe_image.id]),
        json.dumps({'sort_order': 10}),
        content_type='application/json'
    )
    assert response.status_code == 200

    with scopes_disabled():
        recipe_image.refresh_from_db()
        assert recipe_image.sort_order == 10


def test_delete_image(recipe_1_s1, u1_s1):
    """Test deleting an image."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        recipe_image = get_recipe_image(recipe_1_s1, user)
        image_id = recipe_image.id

    response = u1_s1.delete(reverse(DETAIL_URL, args=[image_id]))
    assert response.status_code == 204

    with scopes_disabled():
        assert not RecipeImage.objects.filter(pk=image_id).exists()


# ==================== CUSTOM ACTION TESTS ====================

def test_set_primary(recipe_1_s1, u1_s1):
    """Test setting an image as primary."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        recipe_image = get_recipe_image(recipe_1_s1, user, is_primary=False)

    response = u1_s1.put(
        reverse('api:recipeimage-set-primary', args=[recipe_image.id])
    )
    assert response.status_code == 200

    with scopes_disabled():
        recipe_image.refresh_from_db()
        assert recipe_image.is_primary is True


def test_set_primary_unsets_others(recipe_1_s1, u1_s1):
    """Test that setting primary unsets other primary images."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        image1 = get_recipe_image(recipe_1_s1, user, is_primary=True)
        image2 = get_recipe_image(recipe_1_s1, user, is_primary=False)

    # Set image2 as primary
    response = u1_s1.put(
        reverse('api:recipeimage-set-primary', args=[image2.id])
    )
    assert response.status_code == 200

    with scopes_disabled():
        image1.refresh_from_db()
        image2.refresh_from_db()
        assert image1.is_primary is False
        assert image2.is_primary is True


def test_reorder_images(recipe_1_s1, u1_s1):
    """Test reordering images via custom action."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        image1 = get_recipe_image(recipe_1_s1, user, sort_order=0)
        image2 = get_recipe_image(recipe_1_s1, user, sort_order=1)
        image3 = get_recipe_image(recipe_1_s1, user, sort_order=2)

    # Reorder: image3, image1, image2
    new_order = [image3.id, image1.id, image2.id]
    response = u1_s1.put(
        reverse('api:recipeimage-reorder'),
        json.dumps({'recipe': recipe_1_s1.id, 'order': new_order}),
        content_type='application/json'
    )
    assert response.status_code == 200

    with scopes_disabled():
        image1.refresh_from_db()
        image2.refresh_from_db()
        image3.refresh_from_db()
        assert image3.sort_order == 0
        assert image1.sort_order == 1
        assert image2.sort_order == 2


def test_reorder_requires_recipe(u1_s1):
    """Test that reorder requires recipe parameter."""
    response = u1_s1.put(
        reverse('api:recipeimage-reorder'),
        json.dumps({'order': [1, 2, 3]}),
        content_type='application/json'
    )
    assert response.status_code == 400


# ==================== MODEL BEHAVIOR TESTS ====================

def test_first_image_is_primary(recipe_1_s1, u1_s1):
    """Test that first image is automatically set as primary."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        # Create first image without specifying is_primary
        image1 = RecipeImage.objects.create(
            recipe=recipe_1_s1,
            created_by=user,
        )
        assert image1.is_primary is True

        # Create second image - should not be primary
        image2 = RecipeImage.objects.create(
            recipe=recipe_1_s1,
            created_by=user,
        )
        assert image2.is_primary is False


def test_image_ordering(recipe_1_s1, u1_s1):
    """Test that images are ordered by sort_order, then pk."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        image1 = get_recipe_image(recipe_1_s1, user, sort_order=2)
        image2 = get_recipe_image(recipe_1_s1, user, sort_order=0)
        image3 = get_recipe_image(recipe_1_s1, user, sort_order=1)

        images = list(RecipeImage.objects.filter(recipe=recipe_1_s1))
        assert images[0].id == image2.id  # sort_order=0
        assert images[1].id == image3.id  # sort_order=1
        assert images[2].id == image1.id  # sort_order=2


# ==================== INTEGRATION TESTS ====================

def test_recipe_includes_images(recipe_1_s1, u1_s1):
    """Test that recipe serializer includes images field."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        get_recipe_image(recipe_1_s1, user)
        get_recipe_image(recipe_1_s1, user)

    response = u1_s1.get(reverse('api:recipe-detail', args=[recipe_1_s1.id]))
    data = json.loads(response.content)

    assert 'images' in data
    assert len(data['images']) == 2


def test_primary_image_in_recipe(recipe_1_s1, u1_s1):
    """Test that primary image is correctly identified in recipe."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        image1 = get_recipe_image(recipe_1_s1, user, is_primary=True)
        get_recipe_image(recipe_1_s1, user, is_primary=False)

    response = u1_s1.get(reverse('api:recipe-detail', args=[recipe_1_s1.id]))
    data = json.loads(response.content)

    primary_images = [img for img in data['images'] if img.get('is_primary')]
    assert len(primary_images) == 1
    assert primary_images[0]['id'] == image1.id


# ============================================================================
# Security Tests for secure_image_fetch
# ============================================================================

def test_secure_fetch_blocks_private_ip():
    """Test that secure_image_fetch blocks private IP addresses."""
    from cookbook.helper.HelperFunctions import secure_image_fetch

    private_urls = [
        'http://127.0.0.1/image.jpg',
        'http://192.168.1.1/image.jpg',
        'http://10.0.0.1/image.jpg',
        'http://localhost/image.jpg',
    ]

    for url in private_urls:
        with pytest.raises(ValueError) as exc_info:
            secure_image_fetch(url)
        assert 'security validation' in str(exc_info.value).lower()


def test_secure_fetch_validates_content_type(requests_mock):
    """Test that secure_image_fetch rejects non-image content types."""
    from cookbook.helper.HelperFunctions import secure_image_fetch

    # Mock a URL that returns HTML instead of an image
    requests_mock.get(
        'https://example.com/notanimage',
        text='<html>Not an image</html>',
        headers={'content-type': 'text/html'}
    )

    with pytest.raises(ValueError) as exc_info:
        secure_image_fetch('https://example.com/notanimage')
    assert 'content-type' in str(exc_info.value).lower()


def test_secure_fetch_enforces_size_limit(requests_mock):
    """Test that secure_image_fetch enforces max size limit."""
    from cookbook.helper.HelperFunctions import secure_image_fetch, MAX_IMAGE_SIZE

    # Create content larger than MAX_IMAGE_SIZE
    large_content = b'x' * (MAX_IMAGE_SIZE + 1)

    requests_mock.get(
        'https://example.com/largeimage.jpg',
        content=large_content,
        headers={'content-type': 'image/jpeg'}
    )

    with pytest.raises(ValueError) as exc_info:
        secure_image_fetch('https://example.com/largeimage.jpg')
    assert 'size' in str(exc_info.value).lower()


# ============================================================================
# Data Integrity Tests
# ============================================================================

def test_delete_primary_promotes_next(recipe_1_s1, u1_s1):
    """Test that deleting primary image promotes the next image to primary."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        image1 = get_recipe_image(recipe_1_s1, user, is_primary=True, sort_order=0)
        image2 = get_recipe_image(recipe_1_s1, user, is_primary=False, sort_order=1)

    # Delete primary image
    response = u1_s1.delete(reverse(DETAIL_URL, args=[image1.id]))
    assert response.status_code == 204

    # Verify image2 is now primary
    with scopes_disabled():
        image2.refresh_from_db()
        assert image2.is_primary is True


def test_reorder_invalid_ids_returns_400(recipe_1_s1, u1_s1):
    """Test that reorder endpoint returns 400 for invalid image IDs."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        image1 = get_recipe_image(recipe_1_s1, user)

    response = u1_s1.put(
        reverse('api:recipeimage-reorder'),
        {'recipe': recipe_1_s1.id, 'order': [image1.id, 99999]},  # 99999 doesn't exist
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.content)
    assert 'error' in data
    assert '99999' in str(data['error'])


# ============================================================================
# Edge Case Tests (Phase 4 Remediation)
# ============================================================================

def test_create_without_recipe_returns_400(u1_s1):
    """Test that create without recipe ID returns 400."""
    image_file = create_test_image()
    response = u1_s1.post(
        reverse(LIST_URL),
        {'image': image_file},  # Missing 'recipe' field
        format='multipart'
    )
    assert response.status_code == 400
    data = json.loads(response.content)
    assert 'recipe' in data.get('error', '').lower()


def test_create_invalid_sort_order_returns_400(recipe_1_s1, u1_s1):
    """Test that create with invalid sort_order returns 400."""
    image_file = create_test_image()

    # Test non-integer sort_order
    response = u1_s1.post(
        reverse(LIST_URL),
        {'recipe': recipe_1_s1.id, 'image': image_file, 'sort_order': 'abc'},
        format='multipart'
    )
    assert response.status_code == 400

    # Test negative sort_order
    image_file2 = create_test_image()
    response = u1_s1.post(
        reverse(LIST_URL),
        {'recipe': recipe_1_s1.id, 'image': image_file2, 'sort_order': -5},
        format='multipart'
    )
    assert response.status_code == 400


def test_update_invalid_sort_order_returns_400(recipe_1_s1, u1_s1):
    """Test that update with invalid sort_order returns 400."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        recipe_image = get_recipe_image(recipe_1_s1, user)

    # Test negative sort_order
    response = u1_s1.patch(
        reverse(DETAIL_URL, args=[recipe_image.id]),
        json.dumps({'sort_order': -10}),
        content_type='application/json'
    )
    assert response.status_code == 400

    # Test non-integer sort_order
    response = u1_s1.patch(
        reverse(DETAIL_URL, args=[recipe_image.id]),
        json.dumps({'sort_order': 'invalid'}),
        content_type='application/json'
    )
    assert response.status_code == 400


def test_set_primary_idempotent(recipe_1_s1, u1_s1):
    """Test that setting primary on already primary image is idempotent (returns 200)."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        recipe_image = get_recipe_image(recipe_1_s1, user, is_primary=True)

    # Set primary on already primary image
    response = u1_s1.put(
        reverse('api:recipeimage-set-primary', args=[recipe_image.id])
    )
    assert response.status_code == 200

    with scopes_disabled():
        recipe_image.refresh_from_db()
        assert recipe_image.is_primary is True


def test_reorder_with_duplicate_ids_returns_400(recipe_1_s1, u1_s1):
    """Test that reorder with duplicate IDs in the order list returns 400."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        image1 = get_recipe_image(recipe_1_s1, user)

    response = u1_s1.put(
        reverse('api:recipeimage-reorder'),
        json.dumps({'recipe': recipe_1_s1.id, 'order': [image1.id, image1.id]}),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.content)
    assert 'duplicate' in data.get('error', '').lower()


def test_reorder_with_partial_ids(recipe_1_s1, u1_s1):
    """Test that reorder with only some image IDs succeeds (partial ordering)."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        image1 = get_recipe_image(recipe_1_s1, user, sort_order=0)
        image2 = get_recipe_image(recipe_1_s1, user, sort_order=1)
        image3 = get_recipe_image(recipe_1_s1, user, sort_order=2)

    # Only reorder image2 and image3, leaving image1 out
    response = u1_s1.put(
        reverse('api:recipeimage-reorder'),
        json.dumps({'recipe': recipe_1_s1.id, 'order': [image3.id, image2.id]}),
        content_type='application/json'
    )
    # Should succeed - partial reordering is valid
    assert response.status_code == 200


def test_delete_last_image(recipe_1_s1, u1_s1):
    """Test that deleting the last (and only) image works correctly."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        image = get_recipe_image(recipe_1_s1, user, is_primary=True)
        image_id = image.id

    response = u1_s1.delete(reverse(DETAIL_URL, args=[image_id]))
    assert response.status_code == 204

    # Verify no images remain
    with scopes_disabled():
        assert RecipeImage.objects.filter(recipe=recipe_1_s1).count() == 0


def test_create_with_image_url_invalid_url(recipe_1_s1, u1_s1):
    """Test that create with invalid image_url returns 400."""
    response = u1_s1.post(
        reverse(LIST_URL),
        json.dumps({'recipe': recipe_1_s1.id, 'image_url': 'http://127.0.0.1/malicious.jpg'}),
        content_type='application/json'
    )
    assert response.status_code == 400
    data = json.loads(response.content)
    assert 'security' in data.get('error', '').lower() or 'validation' in data.get('error', '').lower()


def test_unique_primary_constraint(recipe_1_s1, u1_s1):
    """Test that database constraint prevents multiple primary images."""
    with scopes_disabled():
        user = auth.get_user(u1_s1)
        # Create first primary image
        image1 = RecipeImage.objects.create(
            recipe=recipe_1_s1,
            created_by=user,
            is_primary=True
        )

        # Try to create second primary - model save() should demote first
        image2 = RecipeImage.objects.create(
            recipe=recipe_1_s1,
            created_by=user,
            is_primary=True
        )

        image1.refresh_from_db()
        assert image1.is_primary is False
        assert image2.is_primary is True


def test_secure_fetch_redirect_depth_limit(requests_mock):
    """Test that secure_image_fetch limits redirect chains."""
    from cookbook.helper.HelperFunctions import secure_image_fetch, MAX_REDIRECTS

    # Create a chain of redirects longer than MAX_REDIRECTS
    for i in range(MAX_REDIRECTS + 2):
        requests_mock.get(
            f'https://example.com/redirect{i}',
            status_code=302,
            headers={'Location': f'https://example.com/redirect{i+1}'}
        )

    with pytest.raises(ValueError) as exc_info:
        secure_image_fetch('https://example.com/redirect0')
    assert 'redirect' in str(exc_info.value).lower()


def test_create_nonexistent_recipe_returns_404(u1_s1):
    """Test that create with non-existent recipe ID returns 404."""
    image_file = create_test_image()
    response = u1_s1.post(
        reverse(LIST_URL),
        {'recipe': 999999, 'image': image_file},
        format='multipart'
    )
    assert response.status_code == 404
