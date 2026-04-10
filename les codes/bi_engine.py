def calculate_score(prix, qualite, delai_livraison, disponible,
                    prix_max=1000, delai_max=30):
    """
    Calculates a BI score between 0 and 1 for an offer.

    Criteria weights:
      - Price       35%  (lower is better)
      - Quality     40%  (higher is better, out of 5)
      - Delivery    15%  (fewer days is better)
      - Availability 10% (1 if available, 0 if not)
    """

    # Normalize each criterion to a 0-1 scale
    score_prix       = 1 - (prix / prix_max)          # lower price = higher score
    score_qualite    = qualite / 5                     # quality out of 5
    score_delai      = 1 - (delai_livraison / delai_max)  # fewer days = higher score
    score_dispo      = 1 if disponible else 0

    # Clamp values between 0 and 1
    score_prix  = max(0, min(1, score_prix))
    score_delai = max(0, min(1, score_delai))

    # Weighted total
    total = (
        score_prix    * 0.35 +
        score_qualite * 0.40 +
        score_delai   * 0.15 +
        score_dispo   * 0.10
    )

    return round(total, 4)


def rank_offers(offers):
    """
    Takes a list of offer dicts, adds a 'score' field to each,
    and returns them sorted best score first.
    """
    for offer in offers:
        offer["score"] = calculate_score(
            prix=offer["prix"],
            qualite=offer["qualite"],
            delai_livraison=offer["delai_livraison"],
            disponible=offer["disponible"]
        )

    return sorted(offers, key=lambda x: x["score"], reverse=True)

if __name__ == "__main__":
    test = [
        {"prix": 200, "qualite": 4, "delai_livraison": 7,  "disponible": True},
        {"prix": 500, "qualite": 5, "delai_livraison": 3,  "disponible": True},
        {"prix": 150, "qualite": 2, "delai_livraison": 20, "disponible": False},
    ]
    ranked = rank_offers(test)
    for o in ranked:
        print(o)