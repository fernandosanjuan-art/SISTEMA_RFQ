# drawing_context_parser.py

def associate_materials_to_parts(
    parts,
    candidates,
    text
):

    associations = []

    for part in parts:

        part_pos = text.find(part)

        closest = None

        closest_distance = 999999

        for candidate in candidates:

            candidate_pos = candidate["position"]

            distance = abs(
                candidate_pos - part_pos
            )

            if distance < closest_distance:

                closest_distance = distance

                closest = candidate

        associations.append({

            "part_number": part,

            "candidate": closest
        })

    return associations