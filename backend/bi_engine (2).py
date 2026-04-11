def calculate_score(prix, qualite, delai_livraison, fiabilite,
                    prix_max=1000, delai_max=30):
    """
    Calculates a BI score between 0 and 1 for an offer.

    Based on CDC v3.0 Section 4.3:
    - Price       40%  (lower is better)
    - Quality     35%  (higher is better, out of 5)
    - Delivery    10%  (fewer days is better)
    - Reliability 15%  (fiabilite, based on reviews)
    """

    # Convert Decimal to float (fix for MySQL Decimal type)
    prix = float(prix)
    qualite = float(qualite)
    delai_livraison = float(delai_livraison)
    fiabilite = float(fiabilite)

    # Normalize each criterion to a 0-1 scale
    score_prix = 1 - (prix / prix_max)  # lower price = higher score
    score_qualite = qualite / 5  # quality out of 5
    score_delai = 1 - (delai_livraison / delai_max)  # fewer days = higher score
    score_fiabilite = fiabilite / 5  # fiabilite out of 5

    # Clamp values between 0 and 1
    score_prix = max(0, min(1, score_prix))
    score_delai = max(0, min(1, score_delai))
    score_fiabilite = max(0, min(1, score_fiabilite))

    # Weighted total per CDC v3.0
    total = (
            score_prix * 0.40 +  # 40% price
            score_qualite * 0.35 +  # 35% quality
            score_delai * 0.10 +  # 10% delivery
            score_fiabilite * 0.15  # 15% reliability (avis)
    )

    return round(total, 4)


def rank_offers(offers):
    """
    Takes a list of offer dicts, adds a 'score' field to each,
    and returns them sorted best score first.
    """
    for offer in offers:
        # Convert Decimal to float for all numeric values
        prix = float(offer.get("prix", 0))
        qualite = float(offer.get("qualite", 0))
        delai_livraison = float(offer.get("delai_livraison", 0))
        fiabilite = float(offer.get("fiabilite", 3.0))

        offer["score"] = calculate_score(
            prix=prix,
            qualite=qualite,
            delai_livraison=delai_livraison,
            fiabilite=fiabilite
        )

    return sorted(offers, key=lambda x: x["score"], reverse=True)


if __name__ == "__main__":
    test = [
        {"prix": 200, "qualite": 4, "delai_livraison": 7, "fiabilite": 4.5},
        {"prix": 500, "qualite": 5, "delai_livraison": 3, "fiabilite": 4.0},
        {"prix": 150, "qualite": 2, "delai_livraison": 20, "fiabilite": 2.5},
    ]
    ranked = rank_offers(test)
    print("Ranked offers (best first):")
    for i, o in enumerate(ranked, 1):
        print(
            f"{i}. Price: {o['prix']} TND | Quality: {o['qualite']}/5 | Fiabilite: {o['fiabilite']}/5 | Score: {o['score']}")