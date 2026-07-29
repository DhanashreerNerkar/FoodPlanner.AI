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


def test_jain_ambient_bans_onion_garlic():
    profile = UserProfile(
        diet_type="vegetarian",
        cultural_constraints=["jain"],
        ambient_rules=["no onion", "no garlic"],
    )
    banned = banned_ingredients_for_profile(profile)
    assert "onion" in banned
    assert "garlic" in banned
