"""Which recipes count as a meal (spec 10.2).

A pantry can be genuinely dinner-capable and still return nothing but sides. Real main
courses carry ten or twelve ingredients, so owning five of them scores about 42% and falls
under `MIN_MATCH_PERCENT`; a three-ingredient side scores 100%. The floor therefore favours
short recipes, and short recipes are sides — so the cook sees a page of garnishes and
nothing explaining why dinner is missing.

Splitting the results needs only the `category` TheMealDB already gives us, which is
imported into `recipes.category`. It is a lookup against the short list below, not a
judgment: counting for facts (spec section 4).

A generated recipe (F8) has no category at all, and counts as a meal. It was written from
the whole pantry to be cooked as a dish, and it is the answer offered when no meal matches
— so it would be perverse to file it under sides.
"""

# TheMealDB's own category names. Everything else it ships — Chicken, Beef, Seafood, Pasta,
# Vegetarian, Breakfast and so on — is a meal, which is why this is a deny-list: a category
# added upstream should default to being dinner rather than silently vanishing from the
# meals group.
NON_MEAL_CATEGORIES: tuple[str, ...] = ("Side", "Starter", "Dessert")
