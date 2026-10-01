import os
import random

import numpy as np
import psycopg
from dotenv import load_dotenv
from faker import Faker

from services.common.vin import generate_vin

load_dotenv()
SEED, N_FLEETS, N_VEHICLES = 42, 200, 100_000
MODELS = [("Toyota", "Hilux"), ("Tata", "Ace"), ("Mahindra", "Bolero"),
          ("Maruti", "Eeco"), ("Hyundai", "Creta"), ("Ford", "Transit"),
          ("Volvo", "FH"), ("Honda", "City")]


def fleet_of(i: int) -> int:
    return (i % N_FLEETS) + 1


def copy_rows(cur, table, cols, rows):
    with cur.copy(f"COPY {table} ({', '.join(cols)}) FROM STDIN") as cp:
        for row in rows:
            cp.write_row(row)


def main():
    rng = random.Random(SEED)
    risks = np.random.default_rng(SEED).beta(2, 8, N_VEHICLES)
    Faker.seed(SEED)
    fake = Faker()
    ids = range(1, N_VEHICLES + 1)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE fleet, vehicle_model RESTART IDENTITY CASCADE")
        copy_rows(cur, "fleet", ["fleet_id", "name"],
                  ((i, f"Fleet {i:03d}") for i in range(1, N_FLEETS + 1)))
        copy_rows(cur, "vehicle_model", ["model_id", "make", "model"],
                  ((i, mk, md) for i, (mk, md) in enumerate(MODELS, 1)))
        copy_rows(cur, "driver", ["driver_id", "fleet_id", "full_name"],
                  ((i, fleet_of(i), fake.name()) for i in ids))
        copy_rows(cur, "sim_driver_truth", ["driver_id", "risk_level"],
                  ((i, float(risks[i - 1])) for i in ids))
        seen: set[str] = set()

        def vehicles():
            for i in ids:
                vin = generate_vin(rng)
                while vin in seen:
                    vin = generate_vin(rng)
                seen.add(vin)
                yield (vin, fleet_of(i), i, rng.randint(1, len(MODELS)))

        copy_rows(cur, "vehicle", ["vin", "fleet_id", "driver_id", "model_id"],
                  vehicles())
        for table, col in [("fleet", "fleet_id"), ("driver", "driver_id"),
                           ("vehicle_model", "model_id")]:
            cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', "
                        f"'{col}'), (SELECT MAX({col}) FROM {table}))")
    print("Seeded", N_VEHICLES, "vehicles")


if __name__ == "__main__":
    main()