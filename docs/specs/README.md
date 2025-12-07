# Multi-Image Recipe Feature - Specification Documents

## Reading Order

Read these documents in order:

### 1. `MULTI_IMAGE_RECIPE_SPECIFICATION.md` (Start Here)
- Overview and goals
- Architecture decisions
- Database schema design
- API specification
- Task descriptions and dependencies
- Testing requirements

### 2. `MULTI_IMAGE_IMPLEMENTATION_DETAILS.md` (Copy-Paste Code)
- Complete, working code for most tasks
- Task 0: Environment setup
- Tasks 1, 3, 5, 6, 7, 8, 9, 10, 15

### 3. `MULTI_IMAGE_ADDENDUM.md` (Corrections & Missing Tasks)
- Test file naming correction
- Missing tasks: 2, 4, 11, 12, 13, 14
- Corrected task execution order
- Pre-implementation checklist
- Verification commands

## Quick Start for Implementers

```bash
# 1. Read the spec for context
cat docs/specs/MULTI_IMAGE_RECIPE_SPECIFICATION.md

# 2. Follow Task Dependency Order from ADDENDUM:
#    Backend: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 15
#    Frontend: 10 → 13 → 14 → 8 → 9 → 11 → 12

# 3. Copy code from IMPLEMENTATION_DETAILS for tasks 1,3,5,6,7,8,9,10,15
# 4. Copy code from ADDENDUM for tasks 2,4,11,12,13,14

# 5. Verify after each task using commands in ADDENDUM
```

## File Summary

| File | Lines | Purpose |
|------|-------|---------|
| `MULTI_IMAGE_RECIPE_SPECIFICATION.md` | 1,801 | Architecture, design, task descriptions |
| `MULTI_IMAGE_IMPLEMENTATION_DETAILS.md` | 1,679 | Complete code implementations |
| `MULTI_IMAGE_ADDENDUM.md` | 284 | Corrections and missing pieces |
| **Total** | **3,764** | |

## Tasks Covered

| Task | Description | Code Location |
|------|-------------|---------------|
| 0 | Environment Setup | IMPLEMENTATION_DETAILS |
| 1 | Create Model | IMPLEMENTATION_DETAILS |
| 2 | Create Migration | ADDENDUM |
| 3 | Create Serializer | IMPLEMENTATION_DETAILS |
| 4 | Update RecipeSerializer | ADDENDUM |
| 5 | Create ViewSet | IMPLEMENTATION_DETAILS |
| 6 | Register URLs | IMPLEMENTATION_DETAILS |
| 7 | Django Admin | IMPLEMENTATION_DETAILS |
| 8 | RecipeImageManager.vue | IMPLEMENTATION_DETAILS |
| 9 | RecipeImageGallery.vue | IMPLEMENTATION_DETAILS |
| 10 | useFileApi.ts | IMPLEMENTATION_DETAILS |
| 11 | Update RecipeEditor.vue | ADDENDUM |
| 12 | Update RecipeView.vue | ADDENDUM |
| 13 | TypeScript Types | ADDENDUM |
| 14 | Translation Strings | ADDENDUM |
| 15 | Backend Tests | IMPLEMENTATION_DETAILS |
| 16 | Frontend Tests | Optional (not detailed) |
