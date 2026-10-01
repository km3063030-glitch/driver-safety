from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from services.scoring.scores import WEIGHTS, get_client

W = 45          # window length in seconds (stands in for "one week")
MIN_KM = 0.1
TOP_FRAC = 0.2   # label: worst 20% next window
SQL = """
SELECT vin, intDiv(toUnixTimestamp(ts), {w:UInt32}) AS b,
       countIf(evt='HARSH_BRAKE') hb, countIf(evt='HARSH_ACCEL') ha,
       countIf(evt='HARSH_CORNER') hc, countIf(evt='OVERSPEED') os,
       max(odo_km) - min(odo_km) km,
       avg(speed_kmh) avg_speed, max(speed_kmh) max_speed
FROM telemetry.events FINAL
GROUP BY vin, b
"""
FEATURES = ["hb", "ha", "hc", "os", "km", "rate", "avg_speed", "max_speed", "hist_rate"]


def build():
    df = get_client().query_df(SQL, parameters={"w": W})
    print("rows:", len(df), "windows:", df.b.nunique() if len(df) else 0)
    df["wt"] = (WEIGHTS["HARSH_BRAKE"] * df.hb + WEIGHTS["HARSH_ACCEL"] * df.ha
                + WEIGHTS["HARSH_CORNER"] * df.hc + WEIGHTS["OVERSPEED"] * df.os)
    df = df.sort_values(["vin", "b"])
    df["cum_w"] = df.groupby("vin").wt.cumsum()
    df["cum_km"] = df.groupby("vin").km.cumsum()
    df["hist_rate"] = df.cum_w / df.cum_km.clip(lower=0.1) * 100
    df["rate"] = df.wt / df.km.clip(lower=0.1) * 100
    df = df[(df.b > df.b.min()) & (df.b < df.b.max())]   # drop partial edge windows
    df = df[df.km >= MIN_KM]

    nxt = df[["vin", "b", "rate"]].copy()
    nxt["b"] -= 1
    nxt["label"] = nxt.groupby("b").rate.transform(lambda s: s >= s.quantile(1 - TOP_FRAC))
    nxt = nxt.rename(columns={"rate": "rate_next"})
    return df.merge(nxt, on=["vin", "b"])


def precision_at_k(y, score, k):
    order = score.argsort()[::-1][:k]
    return float(y[order].mean())


def main():
    data = build()
    if data.empty:
        raise SystemExit("No window pairs. Need at least 3 time windows of data: "
                         "run the simulator longer or lower W.")
    y = data.label.astype(int).values
    print(f"pairs: {len(data)}  vehicles: {data.vin.nunique()}  positive rate: {y.mean():.2f}")
    train_idx, test_idx = next(GroupShuffleSplit(
        n_splits=1, test_size=0.3, random_state=0).split(data, y, groups=data.vin))
    X = data[FEATURES].values
    k = max(1, int(0.1 * len(test_idx)))

    baseline = (data.hb / data.km).values[test_idx]
    results = {"baseline (harsh brakes/km)": baseline}
    for name, model in [
        ("logistic regression", make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))),
        ("gradient boosting", GradientBoostingClassifier(random_state=0)),
    ]:
        model.fit(X[train_idx], y[train_idx])
        results[name] = model.predict_proba(X[test_idx])[:, 1]

    print(f"{'model':32s} {'AUC':>6s} {'P@10%':>7s}")
    for name, s in results.items():
        print(f"{name:32s} {roc_auc_score(y[test_idx], s):6.3f} "
              f"{precision_at_k(y[test_idx], s, k):7.3f}")
    print(f"random precision would be about {y[test_idx].mean():.2f}")


if __name__ == "__main__":
    main()