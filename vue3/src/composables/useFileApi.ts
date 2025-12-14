import {useDjangoUrls} from "@/composables/useDjangoUrls";
import {ref} from "vue";
import {getCookie} from "@/utils/cookie";
import {AiProvider, RecipeFromSourceResponseFromJSON, RecipeImageFromJSON, ResponseError, UserFile, UserFileFromJSON} from "@/openapi";
import {tr} from "vuetify/locale";
import type {RecipeImageItem} from "@/types/RecipeImage";

/**
 * Maps API response JSON to RecipeImageItem type
 * @param data Raw JSON data from API response
 * @returns RecipeImageItem object
 */
function mapRecipeImageResponse(data: any): RecipeImageItem {
    return {
        id: data.id,
        recipe: data.recipe,
        image: data.image,
        isPrimary: data.is_primary,
        sortOrder: data.sort_order,
        createdAt: data.created_at ? new Date(data.created_at) : undefined,
        createdBy: data.created_by
    }
}

/**
 * function to upload files to the multipart endpoints accepting file uploads
 */
export function useFileApi() {
    const {getDjangoUrl} = useDjangoUrls()

    const fileApiLoading = ref(false)

    /**
     * creates or updates an existing UserFile if an id is given
     * @param name name to set for user file
     * @param file file object to upload
     * @param id optional id to update existing user file
     */
    function createOrUpdateUserFile(name: string, file: File | null, id?: number): Promise<UserFile> {
        let formData = new FormData()
        formData.append('name', name)

        if (file != null) {
            formData.append('file', file)
        }

        fileApiLoading.value = true

        let fetchUrl = getDjangoUrl('api/user-file/')
        let fetchMethod = 'POST'
        if (id) {
            fetchUrl += `${id}/`
            fetchMethod = 'PUT'
        }

        return fetch(fetchUrl, {
            method: fetchMethod,
            headers: {'X-CSRFToken': getCookie('csrftoken')},
            body: formData
        }).then(r => {
            if (r.ok) {
                return r.json().then(r => {
                    return UserFileFromJSON(r)
                })
            } else {
                throw new ResponseError(r)
            }
        }).finally(() => {
            fileApiLoading.value = false
        })
    }

    /**
     * update a recipes image either by a given file or given url
     * @param recipeId ID of recipe to update
     * @param file file object to upload or null to delete image (if no imageUrl is given)
     * @param imageUrl url of an image to download by server
     */
    function updateRecipeImage(recipeId: number, file: File | null, imageUrl?: string) {
        let formData = new FormData()
        if (file != null) {
            formData.append('image', file)
        }
        if (imageUrl) {
            formData.append('image_url', imageUrl)
        }

        return fetch(getDjangoUrl(`api/recipe/${recipeId}/image/`), {
            method: 'PUT',
            headers: {'X-CSRFToken': getCookie('csrftoken')},
            body: formData
        }).then(r => {
            return r.json().then(r => {
                return RecipeImageFromJSON(r)
            })
        }).finally(() => {
            fileApiLoading.value = false
        })
    }

    /**
     * uploads the given file to the image recognition endpoint
     * @param file file object to upload
     * @param text text to import
     * @param recipeId id of a recipe to use as import base (for external recipes
     */
    function doAiImport(providerId: number, file: File | null, text: string = '', recipeId: string = '') {
        let formData = new FormData()

        if (file != null) {
            formData.append('file', file)
        } else {
            formData.append('file', '')
        }
        formData.append('text', text)
        formData.append('recipe_id', recipeId)
        formData.append('ai_provider_id', providerId)
        fileApiLoading.value = true

        return fetch(getDjangoUrl(`api/ai-import/`), {
            method: 'POST',
            headers: {'X-CSRFToken': getCookie('csrftoken')},
            body: formData
        }).then(r => {
            return r.json().then(r => {
                return RecipeFromSourceResponseFromJSON(r)
            })
        }).finally(() => {
            fileApiLoading.value = false
        })
    }

    /**
     * uploads the given files to the app import endpoint
     * @param files array to import
     * @param app app to import
     * @param includeDuplicates if recipes that were found as duplicates should be imported as well
     * @param mealPlans if meal plans should be imported
     * @param shoppingLists if shopping lists should be imported
     * @param nutritionPerServing if nutrition information should be treated as per serving (if false its treated as per recipe)
     * @returns Promise resolving to the import ID of the app import
     */
    function doAppImport(files: File[], app: string, includeDuplicates: boolean, mealPlans: boolean = true, shoppingLists: boolean = true, nutritionPerServing: boolean = false,) {
        fileApiLoading.value = true

        let formData = new FormData()
        formData.append('type', app);
        formData.append('duplicates', includeDuplicates ? 'true' : 'false')
        formData.append('meal_plans', mealPlans ? 'true' : 'false')
        formData.append('shopping_lists', shoppingLists ? 'true' : 'false')
        formData.append('nutrition_per_serving', nutritionPerServing ? 'true' : 'false')
        files.forEach(file => {
            formData.append('files', file)
        })

        return fetch(getDjangoUrl(`api/import/`), {
            method: 'POST',
            headers: {'X-CSRFToken': getCookie('csrftoken')},
            body: formData
        }).then(r => {
            return r.json().then(r => {
                return r.import_id
            })
        }).finally(() => {
            fileApiLoading.value = false
        })
    }

    /**
     * Add a new image to a recipe's image gallery
     * @param recipeId ID of recipe to add image to
     * @param file file object to upload
     * @param imageUrl url of an image to download by server
     * @param isPrimary whether this image should be the primary image
     * @param sortOrder order of the image in the gallery
     */
    function addRecipeImage(recipeId: number, file: File | null, imageUrl?: string, isPrimary: boolean = false, sortOrder: number = 0): Promise<RecipeImageItem> {
        let formData = new FormData()
        formData.append('recipe', recipeId.toString())
        if (file != null) {
            formData.append('image', file)
        }
        if (imageUrl) {
            formData.append('image_url', imageUrl)
        }
        formData.append('is_primary', isPrimary.toString())
        formData.append('sort_order', sortOrder.toString())

        fileApiLoading.value = true

        return fetch(getDjangoUrl(`api/recipe-image/`), {
            method: 'POST',
            headers: {'X-CSRFToken': getCookie('csrftoken')},
            body: formData
        }).then(r => {
            if (r.ok) {
                return r.json().then(mapRecipeImageResponse)
            } else {
                throw new ResponseError(r)
            }
        }).finally(() => {
            fileApiLoading.value = false
        })
    }

    /**
     * Update an existing recipe image
     * @param imageId ID of the recipe image to update
     * @param file new file object to upload
     * @param isPrimary whether this image should be the primary image
     * @param sortOrder order of the image in the gallery
     */
    function updateRecipeGalleryImage(imageId: number, file?: File, isPrimary?: boolean, sortOrder?: number): Promise<RecipeImageItem> {
        let formData = new FormData()
        if (file) {
            formData.append('image', file)
        }
        if (isPrimary !== undefined) {
            formData.append('is_primary', isPrimary.toString())
        }
        if (sortOrder !== undefined) {
            formData.append('sort_order', sortOrder.toString())
        }

        fileApiLoading.value = true

        return fetch(getDjangoUrl(`api/recipe-image/${imageId}/`), {
            method: 'PUT',
            headers: {'X-CSRFToken': getCookie('csrftoken')},
            body: formData
        }).then(r => {
            if (r.ok) {
                return r.json().then(mapRecipeImageResponse)
            } else {
                throw new ResponseError(r)
            }
        }).finally(() => {
            fileApiLoading.value = false
        })
    }

    /**
     * Delete a recipe image from the gallery
     * @param imageId ID of the recipe image to delete
     */
    function deleteRecipeGalleryImage(imageId: number): Promise<void> {
        fileApiLoading.value = true

        return fetch(getDjangoUrl(`api/recipe-image/${imageId}/`), {
            method: 'DELETE',
            headers: {'X-CSRFToken': getCookie('csrftoken')}
        }).then(r => {
            if (!r.ok) {
                throw new ResponseError(r)
            }
        }).finally(() => {
            fileApiLoading.value = false
        })
    }

    /**
     * Set an image as the primary image for its recipe
     * @param imageId ID of the recipe image to set as primary
     */
    function setRecipeImagePrimary(imageId: number): Promise<RecipeImageItem> {
        fileApiLoading.value = true

        return fetch(getDjangoUrl(`api/recipe-image/${imageId}/set_primary/`), {
            method: 'PUT',
            headers: {'X-CSRFToken': getCookie('csrftoken')}
        }).then(r => {
            if (r.ok) {
                return r.json().then(mapRecipeImageResponse)
            } else {
                throw new ResponseError(r)
            }
        }).finally(() => {
            fileApiLoading.value = false
        })
    }

    /**
     * Reorder images for a recipe
     * @param recipeId ID of the recipe
     * @param order array of image IDs in the desired order
     */
    function reorderRecipeImages(recipeId: number, order: number[]): Promise<void> {
        fileApiLoading.value = true

        return fetch(getDjangoUrl(`api/recipe-image/reorder/`), {
            method: 'PUT',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ recipe: recipeId, order: order })
        }).then(r => {
            if (!r.ok) {
                throw new ResponseError(r)
            }
        }).finally(() => {
            fileApiLoading.value = false
        })
    }

    /**
     * Get all images for a specific recipe
     * @param recipeId ID of the recipe
     */
    function getRecipeImages(recipeId: number): Promise<RecipeImageItem[]> {
        fileApiLoading.value = true

        return fetch(getDjangoUrl(`api/recipe-image/?recipe=${recipeId}`, false), {
            method: 'GET',
            headers: {'X-CSRFToken': getCookie('csrftoken')}
        }).then(r => {
            if (r.ok) {
                return r.json().then(data => {
                    return (data.results || data).map(mapRecipeImageResponse)
                })
            } else {
                throw new ResponseError(r)
            }
        }).finally(() => {
            fileApiLoading.value = false
        })
    }

    return {
        fileApiLoading,
        createOrUpdateUserFile,
        updateRecipeImage,
        doAiImport,
        doAppImport,
        // New multiple image support
        addRecipeImage,
        updateRecipeGalleryImage,
        deleteRecipeGalleryImage,
        setRecipeImagePrimary,
        reorderRecipeImages,
        getRecipeImages
    }
}
