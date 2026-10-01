import psycopg
from scipy.stats import spearmanr

from services.common import config
from services.scoring.scores import compute_scores


def main():
    scores = {row["vin"]: row["score"] for row in compute_scores(days=7)}
    with psycopg.connect(config.DATABASE_URL) as conn:
        rows = conn.execute(
            "SELECT v.vin, t.risk_level FROM vehicle v "
            "JOIN sim_driver_truth t ON t.driver_id = v.driver_id"
        ).fetchall()
    pairs = [(scores[vin], float(risk)) for vin, risk in rows if vin in scores]
    values = [score for score, _ in pairs]
    print("vehicles scored:", len(pairs))
    if not pairs:
        print("No scored vehicles available for correlation.")
        return
    print("score min/max:", min(values), max(values))
    rho, _ = spearmanr(
        [score for score, _ in pairs], [risk for _, risk in pairs]
    )
    print("spearman(score, hidden_risk):", round(rho, 3), "(want clearly negative)")


if __name__ == "__main__":
    main()