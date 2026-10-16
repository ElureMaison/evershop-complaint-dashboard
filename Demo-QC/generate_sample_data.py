#!/usr/bin/env python3
"""
generate_sample_data.py -> data.js

Invented data for the QC board demo. The company (Maple & Moss Group), its
stores, its three suppliers, the staff names and every product are fictional.
Nothing comes from a real business. The seed is fixed, so re-running this
reproduces the published demo exactly.

The workflow it models: a product reaches 5 sales, so we ask our suppliers to
quote it and send QC photos, a size chart and answers about material. The
team compares what each supplier sent against the live listing, asks follow-up
questions, decides who fulfils it (or fails it), fixes the listing, and marks
it Done.
"""
import datetime as dt
import json
import os
import random

SEED = 5051016
AS_OF = dt.date(2026, 10, 16)
rng = random.Random(SEED)

STAGES = ["Supplier does QC", "We review QC", "Supplier replies", "Final updates", "Done"]
COUNTS = {"Supplier does QC": 6, "We review QC": 12, "Supplier replies": 14, "Final updates": 8, "Done": 46}
SUPPLIERS = ["Jadeport", "Harborline", "Northgate"]
STORES = ["Maple & Moss", "Coastline Co."]
TEAM = ["Ines", "Marco", "Priya", "Tomas"]

CATS = {
    "Dresses": (["Wrap Midi Dress", "Tiered Maxi Dress", "Linen Shirt Dress", "Smocked Sundress", "Puff-Sleeve Mini Dress", "Halter Satin Dress"], True, (38, 72)),
    "Tops": (["Boxy Linen Tee", "Ruffle-Collar Blouse", "Ribbed Tank", "Button Henley", "Off-Shoulder Top"], True, (24, 44)),
    "Pants": (["Wide-Leg Jeans", "Barrel Jeans", "Pleated Trousers", "Cargo Pants", "Linen Pull-On Pants"], True, (34, 64)),
    "Outerwear": (["Quilted Jacket", "Belted Trench", "Wool-Look Coat", "Cropped Denim Jacket"], True, (52, 96)),
    "Knitwear": (["Cable Cardigan", "Mock-Neck Sweater", "Chunky Knit Vest"], True, (38, 68)),
    "Swimwear": (["Ruched One-Piece", "Skirted Swim Dress", "Tankini Set"], True, (30, 52)),
    "Home": (["Rattan Wall Mirror", "Moonlight Wall Clock", "LED Curtain Lights", "Woven Throw Blanket", "Ceramic Bud Vases"], False, (26, 80)),
    "Craft": (["Embroidery Card Kit", "Felt Wreath Kit", "Gingerbread House Kit"], False, (19, 42)),
}
SYL = ["la", "ve", "ra", "no", "li", "mar", "sel", "en", "ri", "ta", "so", "lu", "na", "el", "va", "ro", "mi", "ka", "do", "fen", "bel", "cor", "ise", "ora"]
COLORS = [("Sage", "#9aae8c"), ("Ivory", "#e9e2d0"), ("Navy", "#2f3e5c"), ("Rust", "#b5603c"), ("Black", "#2b2b2b"), ("Dusty Rose", "#d4a5a5"), ("Sky", "#9cc3e0"), ("Mustard", "#d6a83a"), ("Olive", "#77794a"), ("Lilac", "#b9a6d6")]
MATERIALS = {
    "Dresses": ["100% cotton", "Linen-viscose blend", "Polyester satin", "95% polyester, 5% spandex"],
    "Tops": ["100% cotton", "Linen-viscose blend", "95% polyester, 5% spandex"],
    "Pants": ["Denim, 98% cotton, 2% elastane", "Linen-viscose blend", "Polyester twill"],
    "Outerwear": ["Polyester shell, polyester fill", "Wool-look polyester blend", "100% cotton denim"],
    "Knitwear": ["Acrylic knit", "Acrylic-wool blend", "Cotton knit"],
    "Swimwear": ["82% nylon, 18% spandex", "Recycled polyester, spandex"],
    "Home": ["Rattan and MDF", "Glass and ABS plastic", "Ceramic", "Cotton-acrylic woven"],
    "Craft": ["Felt and cotton thread", "Paper, felt and beads", "Embroidery cotton and card"],
}

# Body measurements (cm) of a true US size, used for listing charts.
US = {"S": (86, 68, 94), "M": (91, 73, 99), "L": (97, 79, 105), "XL": (103, 85, 111)}

QUESTIONS_POOL = [
    ("Is the colour in the QC photos the same as on the listing photos, in daylight?", None),
    ("Can you measure the bust and length of size M flat, in cm?", None),
    ("Does it have side pockets?", "The QC form already asks the supplier about pockets."),
    ("What is the fabric composition on the care label?", "The QC form already asks for the material."),
    ("Is the lining sewn in or removable?", None),
    ("Does the zip run the full length of the back?", "This shows in the photos. Only ask if the photos really cannot show it."),
    ("Will it arrive in a branded box?", "Nobody returns over this and a factory cannot test it. No need to ask."),
    ("Does the LED string work on AA batteries as well as USB?", None),
    ("Is the mirror glass or acrylic?", None),
    ("Which size chart system do you use: Asian or US?", "The size chart answers sizes and measurements."),
]
AI_NOTES_APPAREL = ["Waist on the {s} chart is 4 cm smaller than our size M: likely runs one size small.", "QC photo 2 shows a centre seam the listing photos don't have.", "Hem length in the QC photos looks shorter than the model shot.", "The colour reads warmer than the listing (more mustard than sage).", "No care label visible in any QC photo."]
AI_NOTES_OTHER = ["The QC photos show a plastic frame; the listing says metal.", "Battery box is visible in the QC photos but not on the listing.", "Item looks about 20% smaller than the lifestyle photo implies.", "Two QC photos show glue marks on the edges."]
IMAGE_EDITS = ["Remove the belt in photo 3 (product ships without it)", "Recolour photo 1 to the real sage shade", "Replace the lifestyle shot: it shows a larger size", "Remove the watermark on photo 4", "Crop out the second product in photo 2"]
NOTES = ["Waiting on the factory to send the fabric composition", "Asked for a daylight photo of the colour", "Second sample on the way, ETA Friday", "Price came in high: asked for a 2-piece price", "Supplier says lining changed since the first batch"]
THREAD = [("{a}", "QC is in from {s}. Photos look close, colour a bit warmer."), ("{s} support", "Hi! Sizes run small, we suggest ordering one size up."), ("{b}", "OK, we'll ship one size up and update the chart."), ("{a}", "Sent the questions to {s}."), ("{s} support", "Fabric is 95% polyester, 5% spandex. Photo of the label attached.")]


def name_for(cat):
    nouns = CATS[cat][0]
    b = (rng.choice(SYL) + rng.choice(SYL) + rng.choice(["", rng.choice(SYL)])).capitalize()
    return f"{b} – {rng.choice(nouns)}"


def chart(shift):
    """A supplier size chart. shift>0 runs small (each label is a smaller body)."""
    rows = []
    sizes = list(US)
    for i, s in enumerate(sizes):
        j = max(0, min(len(sizes) - 1, i - shift))
        b, w, h = US[sizes[j]]
        jitter = lambda v: v + rng.choice([-2, -1, 0, 0, 1, 2])
        rows.append([s, jitter(b - (4 * shift if j == i else 0)), jitter(w - (4 * shift if j == i else 0)), jitter(h - (4 * shift if j == i else 0))])
    return rows


def main():
    products, used, pid = [], set(), 2100
    stage_list = [s for s, n in COUNTS.items() for _ in range(n)]
    rng.shuffle(stage_list)
    for stage in stage_list:
        cat = rng.choice(list(CATS))
        nouns, apparel, (lo, hi) = CATS[cat]
        while True:
            nm = name_for(cat)
            if nm not in used:
                used.add(nm)
                break
        si = STAGES.index(stage)
        age = rng.randint(1, 6) if si == 0 else rng.randint(3, 20) if si < 4 else rng.randint(10, 160)
        if si in (1, 2) and rng.random() < 0.15:
            age = rng.randint(21, 70)  # a few stuck ones
        date = AS_OF - dt.timedelta(days=age)
        colors = rng.sample(COLORS, rng.randint(1, 3))
        price = round(rng.uniform(lo, hi) - 0.01, 2)
        variants = []
        for c, _ in colors:
            for s in (list(US) if apparel else ["One size"]):
                variants.append({"name": f"{c} / {s}" if apparel else c, "price": price if s != "XL" else round(price + 3, 2)})

        listing_mat = rng.choice(MATERIALS[cat])
        sups = []
        n_sup = rng.choice([2, 2, 3])
        for s in SUPPLIERS[:n_sup]:
            got_qc = si > 0 and rng.random() > 0.15
            shift = rng.choice([0, 1, 1, 2]) if apparel else 0
            base_cost = price * rng.uniform(0.15, 0.31)
            sup = {
                "name": s,
                "quote": (("Re-quote · low quality" if rng.random() < 0.12 else "Quote in") if got_qc else ("Cannot source" if rng.random() < 0.35 else "Quote asked")) if si > 0 else "Quote asked",
                "similar": got_qc and rng.random() < 0.1,
                "qc": got_qc,
                "photos": rng.randint(3, 7) if got_qc else 0,
                "size_system": (rng.choice(["Asian", "Asian", "US", None]) if apparel else None) if got_qc else None,
                "chart": chart(shift) if (apparel and got_qc and rng.random() > 0.15) else None,
                "material": (listing_mat if rng.random() < 0.65 else rng.choice(MATERIALS[cat])) if got_qc and rng.random() > 0.2 else None,
                "pockets": (rng.choice(["Yes, 2 side pockets", "No pockets", None]) if cat in ("Dresses", "Pants", "Outerwear") else None) if got_qc else None,
                "chinese_tags": rng.random() < 0.3 if got_qc else None,
                "remark": rng.choice([None, None, "Can ship in 3 days", "MOQ 2 pieces for this price", "Colour slightly lighter in person"]) if got_qc else None,
                "p1": round(base_cost, 2), "p2": round(base_cost * 1.85, 2),
                "answer_h": round(rng.uniform(2, 30), 1),
            }
            if sup["quote"] == "Cannot source":
                sup.update(qc=False, photos=0, chart=None, material=None)
            sups.append(sup)
        if stage == "Supplier does QC":
            for sp in sups:
                sp.update(qc=False, photos=0, chart=None, material=None, pockets=None, chinese_tags=None, remark=None)

        decision = fulfiller = None
        if stage == "Done":
            r = rng.random()
            ok = [sp for sp in sups if sp["qc"]]
            if r < 0.12 or not ok:
                decision = "Failed"
            else:
                decision = "Passed"
                fulfiller = min(ok, key=lambda sp: sp["p1"])["name"]
        elif stage == "Final updates":
            ok = [sp for sp in sups if sp["qc"]]
            if ok:
                decision, fulfiller = "Passed", min(ok, key=lambda sp: sp["p1"])["name"]

        qs = []
        if si >= 1:
            pool = [q for q in QUESTIONS_POOL if apparel or "size" not in q[0].lower() and "bust" not in q[0].lower() and "lining" not in q[0].lower()]
            for text, reason in rng.sample(pool, min(len(pool), rng.randint(2, 4))):
                qs.append({"text": text, "reason": reason, "state": ("sent" if si >= 2 else "suggested") if not reason else "not_needed", "to": [sp["name"] for sp in sups if sp["qc"]][:2]})
        ai = []
        if si >= 1 and any(sp["qc"] for sp in sups):
            pool = AI_NOTES_APPAREL if apparel else AI_NOTES_OTHER
            ai = [t.format(s=rng.choice([sp["name"] for sp in sups])) for t in rng.sample(pool, rng.randint(1, 2))]
        edits = []
        if si >= 3 or (si == 2 and rng.random() < 0.3):
            for t in rng.sample(IMAGE_EDITS, rng.randint(0, 2)):
                edits.append({"text": t, "by": rng.choice(TEAM), "state": "live" if si == 4 else rng.choice(["approved", "requested"])})
        flagged = rng.random() < 0.07
        notes = []
        if flagged or (si in (1, 2) and rng.random() < 0.4):
            notes.append({"by": rng.choice(TEAM), "text": rng.choice(NOTES), "at": (date + dt.timedelta(days=min(age, rng.randint(1, 5)))).isoformat()})
        thread = []
        if si >= 1:
            a, b2 = rng.sample(TEAM, 2)
            s0 = sups[0]["name"]
            for who, t in THREAD[: rng.randint(2, 5)]:
                thread.append({"who": who.format(a=a, b=b2, s=s0), "text": t.format(s=s0)})
        listing_chart = [[s, *US[s]] for s in US] if apparel else None
        products.append({
            "id": f"QC-{pid}", "name": nm, "category": cat, "apparel": apparel, "store": rng.choice(STORES),
            "date": date.isoformat(), "stage": stage, "flagged": flagged, "colors": colors, "price": price,
            "variants": variants, "listing": {"material": listing_mat, "chart": listing_chart, "images": rng.randint(4, 8)},
            "suppliers": sups, "decision": decision, "fulfiller": fulfiller, "questions": qs, "ai": ai,
            "edits": edits, "notes": notes, "thread": thread, "owner": rng.choice(TEAM),
        })
        pid += 1

    products.sort(key=lambda p: p["date"], reverse=True)
    payload = {"as_of": AS_OF.isoformat(), "company": "Maple & Moss Group", "stores": STORES, "suppliers": SUPPLIERS,
               "team": TEAM, "stages": STAGES, "products": products}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write("// Invented sample data -- see generate_sample_data.py\nwindow.QC_BOARD = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"{len(products)} products -> {out}")
    for s in STAGES:
        print(f"  {s:18} {sum(p['stage'] == s for p in products)}")
    print(f"  {'Flagged':18} {sum(p['flagged'] for p in products)}")


if __name__ == "__main__":
    main()
