import type { User } from "@/openapi";

/**
 * Represents an individual image associated with a recipe (supports multiple images per recipe)
 */
export interface RecipeImageItem {
    id?: number;
    recipe: number;
    image?: string | null;
    imageUrl?: string;
    isPrimary?: boolean;
    sortOrder?: number;
    createdAt?: Date;
    createdBy?: User;
}

/**
 * Request payload for creating/updating recipe images
 */
export interface RecipeImageRequest {
    recipe: number;
    image?: File;
    imageUrl?: string;
    isPrimary?: boolean;
    sortOrder?: number;
}

/**
 * Response from reorder endpoint
 */
export interface RecipeImageReorderRequest {
    recipe: number;
    order: number[];
}
