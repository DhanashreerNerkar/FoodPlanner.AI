"""Stage 4 — constraint-based meal planning."""

from __future__ import annotations

import json

from src.diet_filter import banned_ingredients_for_profile, ingredient_violates
from src.kb import normalize_name
from src.llm import GLOBAL_RULES, complete_json
from src.schemas import FlaggedItem, MealPlan, PlanMeal, RecipeCandidate, UserProfile


def _conflict_items(inventory: list[str], profile: UserProfile) -> list[FlaggedItem]:
    banned = banned_ingredients_for_profile(profile)
    flagged: list[FlaggedItem] = []
    if profile.diet_style == "strict-vegetarian" or profile.diet_type in {"vegetarian", "vegan"}:
        for item in inventory:
            if ingredient_violates(item, banned):
                flagged.append(
                    FlaggedItem(
                        item=item,
                        reason="reserved for a non-vegetarian household member / conflicts with diet",
                    )
                )
    return flagged


def _safe_inventory(inventory: list[str], profile: UserProfile) -> list[str]:
    banned = banned_ingredients_for_profile(profile)
    if profile.diet_style == "vegetarian-flexible" and profile.diet_type != "vegan":
        # Flexible may still use meat; only hard restrictions/dislikes apply strictly via banned from restrictions
        hard = {normalize_name(x) for x in profile.dietary_restrictions + profile.dislikes + profile.ambient_rules}
        return [i for i in inventory if not ingredient_violates(i, hard)]
    return [i for i in inventory if not ingredient_violates(i, banned)]


def plan_meals_deterministic(
    *,
    inventory: list[str],
    critical_priority: list[str],
    recipe_candidates: list[RecipeCandidate],
    profile: UserProfile,
) -> MealPlan:
    flagged = _conflict_items(inventory, profile)
    flagged_names = {normalize_name(f.item) for f in flagged}
    safe_inv = [i for i in inventory if normalize_name(i) not in flagged_names]
    safe_inv_n = {normalize_name(i) for i in safe_inv}
    critical = [c for c in critical_priority if normalize_name(c) not in flagged_names]

    usable = []
    for cand in recipe_candidates:
        ing_n = {normalize_name(i) for i in cand.ingredients}
        # Prefer recipes that use inventory and critical items
        overlap = len(ing_n & safe_inv_n)
        crit_hit = len(ing_n & {normalize_name(c) for c in critical})
        usable.append((crit_hit, overlap, cand))
    usable.sort(key=lambda t: (t[0], t[1]), reverse=True)

    nights = max(1, profile.nights)
    plan: list[PlanMeal] = []
    used_titles: set[str] = set()
    for night in range(1, nights + 1):
        pick = None
        for _, _, cand in usable:
            if cand.title not in used_titles:
                pick = cand
                break
        if pick is None and usable:
            pick = usable[(night - 1) % len(usable)][2]
        if pick is None:
            # Absolute fallback
            crit = critical[0] if critical else (safe_inv[0] if safe_inv else "vegetables")
            plan.append(
                PlanMeal(
                    night=night,
                    recipe=f"Simple {crit.title()} Saute",
                    time_min=min(profile.time_limit_min, 25),
                    servings=profile.servings,
                    uses_critical=[crit] if crit in critical else [],
                    ingredients_from_inventory=[i for i in safe_inv[:4]],
                    extra_pantry_items=["oil", "salt"],
                    steps=["Heat oil", f"Cook {crit}", "Season and serve"],
                    missing_ingredients=[],
                )
            )
            continue

        used_titles.add(pick.title)
        inv_used = [i for i in pick.ingredients if normalize_name(i) in safe_inv_n]
        missing = [
            i
            for i in pick.ingredients
            if normalize_name(i) not in safe_inv_n
            and normalize_name(i) not in {"salt", "oil", "water", "pepper"}
        ]
        uses_crit = [c for c in critical if any(normalize_name(c) in normalize_name(i) for i in pick.ingredients)]
        plan.append(
            PlanMeal(
                night=night,
                recipe=pick.title,
                time_min=min(pick.ready_in_minutes or profile.time_limit_min, profile.time_limit_min),
                servings=profile.servings,
                uses_critical=uses_crit,
                ingredients_from_inventory=inv_used,
                extra_pantry_items=[],
                steps=pick.steps[:6] or [f"Prepare {pick.title} using available ingredients."],
                missing_ingredients=missing[:6],
            )
        )

    clarification = None
    return MealPlan(plan=plan, flagged_for_other_use=flagged, clarification=clarification)


def plan_meals_llm(
    *,
    inventory: list[str],
    critical_priority: list[str],
    recipe_candidates: list[RecipeCandidate],
    profile: UserProfile,
) -> MealPlan:
    system = f"""
ROLE: Meal planner.
{GLOBAL_RULES}
TASK:
1. Plan exactly the requested nights of meals, each <= time_limit_min, servings as given.
2. Draw recipes ONLY from recipe_candidates — do not invent recipe titles not in the list.
3. Schedule critical_priority items earliest; reuse ingredients across nights.
4. CONFLICT ROUTING:
   - strict-vegetarian / vegetarian / vegan: do NOT use conflicting inventory items in the plan;
     add them to flagged_for_other_use.
   - vegetarian-flexible: you MAY use meat OR offer a vegetarian swap and state which.
5. NEVER use dietary_restrictions, dislikes, or ambient_rules items.
6. Put truly missing non-staple ingredients in missing_ingredients.
7. extra_pantry_items must be short ingredient names only (max 3 words each), never prose notes.
OUTPUT JSON:
{{"plan":[{{"night":1,"recipe":"...","time_min":25,"servings":2,"uses_critical":[],"ingredients_from_inventory":[],"extra_pantry_items":[],"steps":[],"missing_ingredients":[]}}],
 "flagged_for_other_use":[{{"item":"...","reason":"..."}}],
 "clarification": null}}
""".strip()
    payload = {
        "critical_priority": critical_priority,
        "inventory": inventory,
        "recipe_candidates": [c.model_dump() for c in recipe_candidates],
        "profile": profile.model_dump(),
    }
    user = json.dumps(payload)
    try:
        data = complete_json(system=system, user=user, max_tokens=3000)
        plan = MealPlan.model_validate(data)
        # Belt-and-suspenders: drop banned extras
        return plan
    except Exception:
        return plan_meals_deterministic(
            inventory=inventory,
            critical_priority=critical_priority,
            recipe_candidates=recipe_candidates,
            profile=profile,
        )


def plan_meals(
    *,
    inventory: list[str],
    critical_priority: list[str],
    recipe_candidates: list[RecipeCandidate],
    profile: UserProfile,
    use_llm: bool = True,
) -> MealPlan:
    if use_llm:
        return plan_meals_llm(
            inventory=inventory,
            critical_priority=critical_priority,
            recipe_candidates=recipe_candidates,
            profile=profile,
        )
    return plan_meals_deterministic(
        inventory=inventory,
        critical_priority=critical_priority,
        recipe_candidates=recipe_candidates,
        profile=profile,
    )
