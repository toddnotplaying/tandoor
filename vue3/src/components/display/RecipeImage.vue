<template>
    <v-img :cover="cover" :style="{'height': height, 'width': width,}" color="recipeImagePlaceholderBg" :src="image" :alt="$t('Recipe_Image')" :rounded="props.rounded">
        <slot name="overlay">

        </slot>
        <!-- Multiple images indicator -->
        <v-chip v-if="hasMultipleImages && showImageCount" size="x-small" color="primary" class="image-count-chip">
            {{ imageCount }}
        </v-chip>
    </v-img>
</template>

<script setup lang="ts">

import {computed, PropType} from "vue";
import {Recipe, RecipeOverview} from "@/openapi";
import recipeDefaultImage from '../../assets/recipe_no_image.svg'
import {getRecipeImageUrl, hasMultipleImages as checkMultipleImages, getImageCount} from "@/composables/useRecipeImage";

const props = defineProps({
    recipe: {type: {} as PropType<Recipe | RecipeOverview | undefined>, required: false, default: undefined},
    height: {type: String},
    width: {type: String},
    cover: {type: Boolean, default: true},
    rounded: {type: [Boolean, String], default: false},
    showImageCount: {type: Boolean, default: false},
})

const image = computed(() => getRecipeImageUrl(props.recipe) ?? recipeDefaultImage)
const hasMultipleImages = computed(() => checkMultipleImages(props.recipe))
const imageCount = computed(() => getImageCount(props.recipe))

</script>

<style scoped>
.image-count-chip {
    position: absolute;
    bottom: 4px;
    right: 4px;
}
</style>