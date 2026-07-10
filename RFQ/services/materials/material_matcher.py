# material_matcher.py

from rapidfuzz import fuzz

from RFQ.models import Material


def calculate_material_score(
    candidate,
    db_material
):

    score = 0

    candidate_text = (
        candidate["material"]
        .upper()
    )

    commercial = (
        db_material.commercial_name
        .upper()
    )

    family = (
        db_material.family
        .upper()
    )

    color = (
        db_material.color or ""
    ).upper()

    supplier = (
        db_material.supplier or ""
    ).upper()

    pigment = (
        db_material.pigment or ""
    ).upper()

    # FAMILY

    if family in candidate_text:
        score += 40

    # COMMERCIAL NAME

    commercial_score = fuzz.partial_ratio(
        candidate_text,
        commercial
    )

    score += commercial_score * 0.3

    # COLOR

    if candidate["color"]:

        if candidate["color"] == color:
            score += 15

    # GF

    if candidate["gf"]:

        if (
            db_material.glass_fill and
            int(db_material.glass_fill)
            == int(candidate["gf"])
        ):
            score += 10

    # SUPPLIER

    if candidate["supplier"]:

        if candidate["supplier"] == supplier:
            score += 10

    # PIGMENT

    if candidate["pigment"]:

        if candidate["pigment"] == pigment:
            score += 10

    return score


def match_materials(candidates):

    materials = Material.objects.all()

    results = []

    for candidate in candidates:

        best = None

        best_score = 0

        for db_material in materials:

            score = calculate_material_score(
                candidate,
                db_material
            )

            if score > best_score:

                best_score = score

                best = db_material

        if best and best_score >= 45:

            results.append({

                "candidate": candidate,

                "material": best,

                "score": best_score
            })

    return results