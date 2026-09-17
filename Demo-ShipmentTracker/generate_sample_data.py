"""Generate the sample data behind the shipment dashboard demo.

Every figure on /Demo-ShipmentTracker/ comes from this script. The brand,
markets, orders, gear counts, tracking numbers and issue reasons are all
invented; nothing here is derived from any client's data. Seeded, so re-running
it reproduces the page exactly.

    python3 generate_sample_data.py > demo_data.json
"""
import json, random
random.seed(1729)

BRAND   = "Vantage Team Sports"
MARKETS = ["Austin", "Charlotte", "Denver", "Nashville", "Phoenix", "Portland", "Sacramento"]
SPORTS  = ["Baseball", "Softball", "Soccer", "Volleyball"]
SEASONS = ["Summer", "Fall"]
YEARS   = [2025, 2026]
GEAR    = ["Jerseys", "Pants", "Caps", "Helmets", "Bags", "Hoodies", "Socks"]
REASONS = ["Incorrect team name print", "Wrong size run", "Color mismatch", "Missing numbers", "Torn seam"]

orders = []
oid = 0
for market in MARKETS:
    for _ in range(random.randint(3, 7)):
        oid += 1
        sport  = random.choice(SPORTS)
        season = random.choice(SEASONS)
        year   = random.choice(YEARS)
        num    = random.randint(1, 8)
        phase  = random.choices([1, 2, 3, 4], weights=[10, 18, 20, 52])[0]
        proofs = round(random.uniform(1.5, 9.0), 1)
        ship   = round(proofs + random.uniform(8.0, 26.0), 1)
        transit= round(random.uniform(2.0, 9.0), 1)
        deliv  = round(ship + transit, 1)
        delayed= random.random() < 0.27
        status = random.choices([0, 1, 2], weights=[22, 48, 30])[0]
        orders.append({
            "id": f"o{oid}",
            "label": f"{market} {sport} {season} Order {num}",
            "market": market, "sport": sport, "season": season, "year": year,
            "days_to_proofs": proofs,
            "days_to_ship": ship,
            "days_to_delivery": deliv if phase >= 4 else None,
            "days_ship_to_delivery": transit if phase >= 4 else None,
            "is_delayed": delayed,
            "current_phase": phase,
            "order_status": status,
        })

def items(market, gear, qty, n, with_tn=False, reason=False):
    out = []
    left = qty
    for i in range(n):
        q = left if i == n - 1 else max(1, int(left / (n - i) * random.uniform(.6, 1.4)))
        q = min(q, left); left -= q
        it = {"market": market, "gear_type": gear, "order": random.randint(1, 8), "qty": q}
        if with_tn: it["tn"] = f"1Z{random.randint(10**9, 10**10-1)}"
        if reason:  it["reason"] = random.choice(REASONS)
        out.append(it)
        if left <= 0: break
    return out

markets = {}
for market in MARKETS:
    gears = []
    for g in random.sample(GEAR, random.randint(4, 6)):
        total = random.randint(60, 900)
        arrived = int(total * random.uniform(0, 1))
        shipped = int((total - arrived) * random.uniform(0, .8))
        inprod  = total - arrived - shipped
        err     = random.choice([0, 0, 0, random.randint(2, 28)])
        gears.append({
            "gear_type": g, "total": total,
            "arrived": arrived, "shipped": shipped, "in_production": inprod, "error": err,
            "arrived_items":       items(market, g, arrived, random.randint(1, 3)) if arrived else [],
            "shipped_items":       items(market, g, shipped, random.randint(1, 2), with_tn=True) if shipped else [],
            "in_production_items": items(market, g, inprod,  random.randint(1, 2)) if inprod else [],
            "error_items":         items(market, g, err,     1, reason=True) if err else [],
        })
    tot = sum(g["total"] for g in gears)
    arr = sum(g["arrived"] for g in gears)
    shp = sum(g["shipped"] for g in gears)
    prd = sum(g["in_production"] for g in gears)
    markets[market] = {
        "total": tot, "arrived": arr, "shipped": shp, "in_production": prd,
        "error": sum(g["error"] for g in gears),
        "arrived_pct":       round(arr / tot * 100) if tot else 0,
        "shipped_pct":       round(shp / tot * 100) if tot else 0,
        "in_production_pct": round(prd / tot * 100) if tot else 0,
        "gear": gears,
    }

print(json.dumps({"brand": BRAND, "orders": orders, "markets": markets}))
