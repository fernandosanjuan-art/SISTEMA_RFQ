# weight_estimator.py

import re


def extract_dimensions(text):

    matches = re.findall(
        r'(\d+\.\d+|\d+)',
        text
    )

    dimensions = []

    for match in matches:

        try:

            value = float(match)

            if value > 1:
                dimensions.append(value)

        except:
            pass

    return dimensions


def estimate_volume_from_text(text):

    dimensions = extract_dimensions(text)

    if len(dimensions) < 3:
        return None

    dimensions = sorted(
        dimensions,
        reverse=True
    )

    length = dimensions[0]

    width = dimensions[1]

    thickness = dimensions[-1]

    volume_mm3 = (
        length *
        width *
        thickness
    )

    volume_cm3 = volume_mm3 / 1000

    return round(volume_cm3, 2)


def estimate_weight(
    volume_cm3,
    density
):

    if (
        volume_cm3 is None or
        density is None
    ):
        return None

    weight = (
        volume_cm3 *
        density
    )

    return round(weight, 2)