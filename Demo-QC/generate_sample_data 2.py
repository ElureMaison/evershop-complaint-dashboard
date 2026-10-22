#!/usr/bin/env python3
"""
generate_sample_data.py -> data.js

Sample data for the 5+ Sales QC demo. Everything here is invented: the
company (Maple & Moss Group), its two stores, its two suppliers, every product
name, date and figure. Nothing is scrubbed from a real business. The random
seed is fixed, so re-running this reproduces the published dashboard exactly.

The model: a product enters QC on the day it makes its 5th sale. It then moves
through five stages (supplier does QC -> we review -> supplier replies and
edits -> final updates -> done). A finished product is passed clean, fixed
(the listing was edited), pulled, or has no QC record. The patterns built in
are the ones a QC lead would want to spot: size charts are the most common
fix, one supplier's reports fail more often, and fixed products' refunds grow
more slowly than passed ones.
"""
import datetime as dt
import json
import math
import os
import random

SEED = 20261016
AS_OF = dt.date(2026, 10, 16)
START = dt.date(2026, 4, 1)
N = 480

rng = random.Random(SEED)

STORES = ["Maple & Moss", "Coastline Co."]
SUPPLIERS = ["Jadeport Supply", "Harborline Sourcing"]
STAGES = ["Supplier does QC", "We review QC", "Supplier replies", "Final updates", "Done"]
CHECKS = ["Size", "Colour", "Material", "Photos", "Function"]
EDITS = ["Size chart", "Photos", "Features", "Material", "Description"]

CATEGORIES = {
    # name: (weight, apparel?, price range)
    "Dresses": (16, True, (34, 72)),
    "Tops": (14, True, (22, 44)),
    "Jeans & Pants": (12, True, (32, 64)),
    "Outerwear": (8, True, (48, 96)),
    "Knitwear": (8, True, (36, 68)),
    "Swimwear": (7, True, (28, 52)),
    "Home Decor": (10, False, (24, 80)),
    "Craft Kits": (8, False, (18, 42)),
    "Pet": (6, False, (16, 38)),
    "Accessories": (6, False, (14, 40)),
    "Kitchen": (5, False, (18, 56)),
}
NOUNS = {
    "Dresses": ["Wrap Midi Dress", "Tiered Maxi Dress", "Linen Shirt Dress", "Smocked Sundress", "Ribbed Bodycon Dress", "Puff-Sleeve Mini Dress"],
    "Tops": ["Boxy Linen Tee", "Ruffle-Collar Blouse", "Ribbed Tank", "Button Henley", "Peplum Top", "Off-Shoulder Top"],
    "Jeans & Pants": ["Wide-Leg Jeans", "Barrel Jeans", "Pleated Trousers", "Cargo Pants", "Cropped Flares", "Linen Pull-On Pants"],
    "Outerwear": ["Quilted Jacket", "Belted Trench", "Wool-Look Coat", "Denim Jacket", "Hooded Parka"],
    "Knitwear": ["Cable Cardigan", "Mock-Neck Sweater", "Chunky Knit Vest", "Ribbed Knit Set"],
    "Swimwear": ["Ruched One-Piece", "Skirted Swim Dress", "High-Waist Bikini", "Tankini Set"],
    "Home Decor": ["Rattan Wall Mirror", "Moonlight Wall Clock", "Ceramic Bud Vases", "LED Curtain Lights", "Woven Throw Blanket", "Linen Cushion Covers"],
    "Craft Kits": ["Embroidery Card Kit", "Felt Wreath Kit", "Gingerbread House Kit", "Punch-Needle Kit"],
    "Pet": ["Silent Nail File", "Calming Donut Bed", "Lick Mat Set", "Reflective Harness"],
    "Accessories": ["Wide-Brim Sun Hat", "Woven Tote", "Pearl Hair Clips", "Silk Scrunchie Set"],
    "Kitchen": ["Glass Storage Set", "Bamboo Utensil Set", "Pour-Over Kettle", "Herb Keeper"],
}
SYL = ["la", "ve", "ra", "no", "li", "mar", "sel", "en", "ri", "ta", "so", "lu", "na", "el", "va", "ro", "mi", "ka", "do", "fen", "bel", "cor", "ise", "ora"]
DEFECTS_APPAREL = ["Runs a size small", "Fabric thinner than listed", "Colour differs from photo", "Loose threads", "Uneven stitching", "Zip or button faulty", "Lining missing", "Strong odour on arrival"]
DEFECTS_OTHER = ["Colour differs from photo", "Smaller than listed", "Missing part", "Arrives scratched", "Print misaligned", "Weak battery / LED", "Packaging crushed", "Instructions unclear"]
NOTES = ["Asked for a size-chart measurement on the model", "Waiting on new photos without heavy editing", "Supplier checking the fabric weight", "Re-quote requested: first sample was low quality", "Confirming the LED works on batteries", "Asked for a photo of the real colour in daylight", "Supplier says the lining was changed", "Waiting for a second sample"]


def brand():
    return (rng.choice(SYL) + rng.choice(SYL) + rng.choice(["", rng.choice(SYL)])).capitalize()


def day(d):
    return d.isoformat()


def poisson(lam):
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= l:
            return k
        k += 1


def pick_weighted(d):
    total = sum(v[0] for v in d.values())
    r = rng.uniform(0, total)
    for k, v in d.items():
        r -= v[0]
        if r <= 0:
            return k
    return k


def main():
    products, used = [], set()
    span = (AS_OF - START).days
    for i in range(N):
        cat = pick_weighted(CATEGORIES)
        _, apparel, (lo, hi) = CATEGORIES[cat]
        while True:
            name = f"{brand()} – {rng.choice(NOUNS[cat])}"
            if name not in used:
                used.add(name)
                break
        # More products reach 5 sales later in the year (the stores grew).
        qc = START + dt.timedelta(days=int(span * rng.random() ** 0.7))
        age = (AS_OF - qc).days
        store = STORES[0] if rng.random() < 0.6 else STORES[1]
        supplier = SUPPLIERS[0] if rng.random() < 0.55 else SUPPLIERS[1]
        harbor = supplier == SUPPLIERS[1]
        if rng.random() < 0.07:
            supplier = None

        # Stage: the younger the product, the likelier it is still open.
        p_open = 0.85 if age < 7 else 0.45 if age < 21 else 0.12 if age < 45 else 0.03 if age < 75 else 0
        open_ = rng.random() < p_open
        stage = rng.choice(STAGES[:4]) if open_ else "Done"

        # Stage history: each step takes 1-9 days (longer at the supplier).
        hist, d = [], qc
        last = STAGES.index(stage)
        for s in range(last + 1):
            hist.append([STAGES[s], day(d)])
            d = d + dt.timedelta(days=rng.randint(1, 4) if s in (1, 3) else rng.randint(1, 9))
            if d > AS_OF:
                d = AS_OF

        # Outcome for finished products.
        if open_:
            outcome = "Open"
        else:
            r = rng.random()
            outcome = "No QC record" if (qc < dt.date(2026, 6, 1) and r < 0.35) or r < 0.06 else \
                "Pulled" if r < 0.15 else "Passed clean" if r < (0.40 if not harbor else 0.33) else "Fixed"

        edits = []
        if outcome == "Fixed":
            odds = {"Size chart": 0.72 if apparel else 0.12, "Photos": 0.58 if harbor else 0.38,
                    "Features": 0.12 if apparel else 0.55, "Material": 0.22 if apparel else 0.08, "Description": 0.28}
            edits = [e for e in EDITS if rng.random() < odds[e]] or [rng.choice(EDITS[:3])]

        has_report = outcome not in ("No QC record",) and not (open_ and stage == STAGES[0])
        checks, defects, verdict = {}, [], None
        if has_report:
            fail_bias = 0.10 if harbor else 0.05
            for c in CHECKS:
                linked = {"Size": "Size chart", "Photos": "Photos", "Function": "Features", "Material": "Material", "Colour": "Photos"}[c]
                if c == "Size" and not apparel:
                    checks[c] = "n/a"
                    continue
                p_bad = 0.75 if linked in edits else (0.55 if outcome == "Pulled" else fail_bias)
                checks[c] = "mismatch" if rng.random() < p_bad else ("unknown" if rng.random() < 0.06 else "ok")
            bad = sum(v == "mismatch" for v in checks.values())
            verdict = "fail" if bad >= 2 else "warn" if bad == 1 else "pass"
            pool = DEFECTS_APPAREL if apparel else DEFECTS_OTHER
            defects = rng.sample(pool, min(len(pool), bad + (1 if rng.random() < 0.3 else 0)))

        price = round(rng.uniform(lo, hi), 2)
        cost = round(price * rng.uniform(0.22, 0.34), 2)
        answer_h = round(math.exp(rng.gauss(math.log(11 if harbor else 7), 0.6)), 1)
        quotes = 1 + (rng.random() < 0.25) + (rng.random() < 0.08)

        # Refunds: month 1 after QC, then per-30-day rate in months 2-3.
        # Sales ramp, so every group rises; fixed products rise least.
        base = rng.uniform(0.3, 1.3) * (1.3 if apparel else 0.7)
        m1 = poisson(base) if age >= 30 else None
        growth = {"Fixed": 1.5, "Passed clean": 2.3, "Pulled": 0.4, "No QC record": 2.6, "Open": 2.0}[outcome]
        m23 = round(poisson(base * growth * 2) / 2, 1) if age >= 90 else None
        total_refunds = (m1 or 0) + int((m23 or 0) * 2) + (poisson(base * growth * 0.6 * (age - 90) / 30) if age > 90 else 0)
        refund_eur = round(total_refunds * price * rng.uniform(0.45, 0.75), 2)

        products.append({
            "id": f"P{1000 + i}", "name": name, "category": cat, "store": store, "supplier": supplier,
            "qc": day(qc), "stage": stage, "outcome": outcome, "history": hist,
            "edits": edits, "checks": checks, "verdict": verdict, "defects": defects,
            "price": price, "cost": cost, "answer_h": answer_h, "quotes": quotes,
            "m1": m1, "m23": m23, "refunds": total_refunds, "refund_eur": refund_eur,
            "flagged": rng.random() < 0.04, "note": rng.choice(NOTES) if open_ else None,
        })

    products.sort(key=lambda p: p["qc"], reverse=True)
    payload = {"as_of": day(AS_OF), "generated": "seed %d" % SEED, "company": "Maple & Moss Group",
               "stores": STORES, "suppliers": SUPPLIERS, "stages": STAGES, "checks": CHECKS,
               "edits": EDITS, "products": products}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write("// Invented sample data -- see generate_sample_data.py\nwindow.QC_DATA = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    done = [p for p in products if p["outcome"] != "Open"]
    print(f"{len(products)} products, {len(done)} done, {len(products) - len(done)} open -> {out}")
    for o in ["Passed clean", "Fixed", "Pulled", "No QC record", "Open"]:
        print(f"  {o:14} {sum(p['outcome'] == o for p in products)}")


if __name__ == "__main__":
    main()
