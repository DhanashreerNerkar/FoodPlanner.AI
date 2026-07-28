# FoodPlanner.AI

Purpose
Chabot will have profile of person having details about his dietry and traditiona/cultural eating habits/any other constraints.
A chatbot-based meal-planning assistant that accepts an uploaded or camera-captured fridge/pantry photo as its primary input.
Converts messy, real-world fridge/pantry contents into a multi-day meal plan as asked by user.
Optimizes for waste reduction, prioritizing ingredients closest to spoiling.
Uses that ingredients to search for recipe that can be prepared. 

Target user
Budget- and time-conscious home cooks (students, professionals, parents) planning meals on a weekly cycle.

Requirement 1 — Preference capture (happens first, before any plan is generated)
At session start, capture dietary type (vegetarian, vegan, non-vegetarian, etc.) and cultural/religious eating habits (e.g., halal, kosher, Jain).
Once a restriction is set, it is a hard constraint: no non-vegetarian dishes suggested to a vegetarian user, and no non-vegetarian ingredients allowed inside any suggested dish (including hidden ones like gelatin or fish sauce).

Requirement 2 — Ingredient substitution via home-makeable alternatives
If a required ingredient is missing, don't just suggest a store-bought swap — check whether the user can make it from other things likely at home.
Example: user wants palak paneer but has no paneer. If they have spinach (already flagged as aging) but no paneer, the bot asks whether they have milk or curd on hand.
Bot searches for the ways to make paneer/alternatives to panner. presents that to user and user chooses from given option.
If they select make paneer from milk steps, the bot walks them through making fresh paneer at home: boil milk 2–3 minutes, add an acid (vinegar or lemon juice), strain the curds.
This substitution logic should be a general pattern — recognizable "base ingredients → homemade derivative" chains, not a one-off for paneer keeping in context the users eating constraints

---------------------------------------------------------------------------------------------------------------------
FoodPlanner.AI — Requirements Folded into the Pipeline: 

New Stage 0 — Profile Capture (runs before Stage 1, one per user): Triggered on first session or whenever profile is empty/update profile is clicked; captures diet type (vegetarian/vegan/non-veg) and cultural/religious constraints (halal, kosher, Jain, etc.).
Written to user_profile.json (long-term memory) as a hard constraint, not a preference — every later stage reads it, none can override it.
Also captures ambient rules implied by the diet type up front — e.g., Jain → no onion/garlic/root vegetables — so Stage 4/5 don't have to re-derive them.
Skipped on returning sessions unless the user asks to edit settings.

Stage 1 — Vision Ingestion (unchanged) : Extracts food items from the fridge/pantry photo → confirmed list via user gate.
Stage 2 — Freshness Scoring (unchanged) : Ranks confirmed items 5 (use now) → 1 (shelf-stable) using the shelf-life table.
Stage 3 — Critical-Priority Filter (unchanged, deterministic) : Pulls items scoring ≥4 into critical_priority.
Stage 4 — Meal Planning : Recipe search now filters Spoonacular candidates against the Stage 0 profile before they ever reach the LLM — no non-vegetarian dish or 
          hidden non-veg ingredient (gelatin, fish sauce, lard) can enter recipe_candidates. Plans are built to consume critical_priority items first, same as today.
Stage 5 — Substitution (this is where your new ask lives) : This stage gets restructured from "one compliant swap" into a two-step, profile-aware, interactive flow:
          Trigger: a planned recipe needs an ingredient the user doesn't have (e.g., paneer for palak paneer). Homemade-derivation search (new): before falling back to a 
          generic store-bought substitute, check a new derivation_kb — a table of "base ingredient(s) → homemade derivative" chains 
          (milk/curd → paneer; yeast+flour+time → sourdough starter; cream → butter, etc.). Availability check against inventory: ask/confirm whether the user has the base 
          ingredient(s) needed for the derivation (e.g., "Do you have milk or curd?"). Present options, not a decision: show the user a short list — e.g.,
          "Make paneer from milk," "Make paneer from curd," "Skip and use a different protein" — and let them pick. Diet-constraint filter applied to every option before 
          display: any derivation path or fallback substitute that conflicts with Stage 0's profile is removed from the list before the user ever sees it 
          (never offer a dairy-derived option to a vegan user, for instance). Guided steps on selection: once the user picks an option, the bot returns the step-by-step 
          process (e.g., boil milk 2–3 min → add vinegar/lemon → strain). Refusal (unchanged): if no compliant derivation and no compliant store-bought substitute exists, 
          return the fixed refusal object.
