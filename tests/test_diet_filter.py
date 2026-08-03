"""Unit tests for diet filtering."""

from src.diet_filter import filter_recipe_candidates, banned_ingredients_for_profile
from src.schemas import RecipeCandidate, UserProfile


def test_vegetarian_strips_meat_and_hidden():
    profile = UserProfile(diet_type="vegetarian", diet_style="strict-vegetarian")
    candidates = [
        RecipeCandidate(title="Chicken Kale Bake", ingredients=["chicken", "kale"]),
        RecipeCandidate(title="Spinach Rice", ingredients=["spinach", "rice", "gelatin"]),
        RecipeCandidate(title="Lemon Dal", ingredients=["lentils", "lemon", "cumin"]),
        RecipeCandidate(title="Veg Stir Fry", ingredients=["tofu", "spinach", "fish sauce"]),
    ]
    kept = filter_recipe_candidates(candidates, profile)
    titles = {c.title for c in kept}
    assert titles == {"Lemon Dal"}


def test_vegan_strips_dairy():
    profile = UserProfile(diet_type="vegan", diet_style="none")
    candidates = [
        RecipeCandidate(title="Paneer Curry", ingredients=["paneer", "spinach"]),
        RecipeCandidate(title="Tofu Curry", ingredients=["tofu", "spinach", "oil"]),
    ]
    kept = filter_recipe_candidates(candidates, profile)
    assert [c.title for c in kept] == ["Tofu Curry"]


def test_vegetarian_strips_egg_but_eggetarian_allows_it():
    candidates = [
        RecipeCandidate(title="Egg Fried Rice", ingredients=["rice", "eggs"]),
        RecipeCandidate(title="Tofu Fried Rice", ingredients=["rice", "tofu"]),
    ]

    vegetarian = UserProfile(diet_type="vegetarian", diet_style="strict-vegetarian")
    assert [c.title for c in filter_recipe_candidates(candidates, vegetarian)] == ["Tofu Fried Rice"]

    eggetarian = UserProfile(diet_type="eggetarian")
    assert [c.title for c in filter_recipe_candidates(candidates, eggetarian)] == [
        "Egg Fried Rice",
        "Tofu Fried Rice",
    ]


def test_jain_ambient_bans_onion_garlic():
    profile = UserProfile(
        diet_type="vegetarian",
        cultural_constraints=["jain"],
        ambient_rules=["no onion", "no garlic"],
    )
    banned = banned_ingredients_for_profile(profile)
    assert "onion" in banned
    assert "garlic" in banned


def test_hard_allergy_is_filtered_before_planning():
    profile = UserProfile(diet_type="vegetarian", allergies=["peanuts"])
    candidates = [
        RecipeCandidate(title="Peanut Noodles", ingredients=["noodles", "peanuts"]),
        RecipeCandidate(title="Tofu Noodles", ingredients=["noodles", "tofu"]),
    ]
    assert [c.title for c in filter_recipe_candidates(candidates, profile)] == ["Tofu Noodles"]


def test_vegetarian_requires_explicitly_vegan_kimchi_and_bibimbap():
    profile = UserProfile(diet_type="vegetarian", allergies=["egg"])
    candidates = [
        RecipeCandidate(title="Vegetable Bibimbap", ingredients=["cabbage kimchi", "rice"]),
        RecipeCandidate(title="Vegan Bibimbap", ingredients=["vegan kimchi", "rice"]),
    ]
    assert [c.title for c in filter_recipe_candidates(candidates, profile)] == ["Vegan Bibimbap"]
