import type { Recipe, RecipeOverview, RecipeImageItem } from "@/openapi"

/**
 * Normalized image data structure used throughout the frontend.
 * Uses camelCase to match OpenAPI generated types.
 */
export interface NormalizedRecipeImage {
    image: string
    isPrimary: boolean
    id?: number
    sortOrder?: number
}

/**
 * Type for recipe objects that may have images.
 * Supports both new multi-image system and legacy single image.
 */
type RecipeWithImages = Recipe | RecipeOverview | {
    images?: RecipeImageItem[]
    image?: string
}

/**
 * Type guard to check if recipe has images array
 */
function hasImagesArray(recipe: RecipeWithImages): recipe is RecipeWithImages & { images: RecipeImageItem[] } {
    return 'images' in recipe && Array.isArray(recipe.images) && recipe.images.length > 0
}

/**
 * Get the primary image URL for a recipe.
 * Checks new images array first, falls back to legacy image field.
 *
 * @param recipe Recipe object (can be Recipe, RecipeOverview, or any object with images/image)
 * @returns Image URL string or null if no image
 */
export function getRecipeImageUrl(recipe: RecipeWithImages | null | undefined): string | null {
    if (!recipe) return null

    // Check for new images array first
    if (hasImagesArray(recipe)) {
        const images = recipe.images
        // Find primary image or use first image
        const primaryImage = images.find(img => img.isPrimary)
        if (primaryImage?.image) return primaryImage.image
        if (images[0]?.image) return images[0].image
    }

    // Fallback to legacy image field
    if (recipe.image) return recipe.image

    return null
}

/**
 * Get all images for a recipe as a normalized array.
 * Returns images array if available, or wraps legacy single image.
 *
 * @param recipe Recipe object
 * @returns Array of normalized image objects with { image, isPrimary } shape
 */
export function getRecipeImages(recipe: RecipeWithImages | null | undefined): NormalizedRecipeImage[] {
    if (!recipe) return []

    if (hasImagesArray(recipe)) {
        return recipe.images.map(img => ({
            image: img.image || '',
            isPrimary: img.isPrimary || false,
            id: img.id,
            sortOrder: img.sortOrder
        }))
    }

    // Fallback to legacy single image
    if (recipe.image) {
        return [{ image: recipe.image, isPrimary: true }]
    }

    return []
}

/**
 * Check if recipe has multiple images
 */
export function hasMultipleImages(recipe: RecipeWithImages | null | undefined): boolean {
    if (!recipe) return false
    return hasImagesArray(recipe) && recipe.images.length > 1
}

/**
 * Get the count of images for a recipe
 */
export function getImageCount(recipe: RecipeWithImages | null | undefined): number {
    if (!recipe) return 0
    if (hasImagesArray(recipe)) return recipe.images.length
    return recipe.image ? 1 : 0
}
