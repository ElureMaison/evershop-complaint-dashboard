#!/usr/bin/env python3
"""
generate_sample_data.py -> data.js

Invented data for the Unfulfilled Orders demo. The retail group (Northfield
Collective), its three stores, its two suppliers, every customer, address,
order number and tracking number are fictional. Nothing comes from a real
business. The seed is fixed, so re-running this reproduces the published demo.

The workflow it models: an order is paid but not yet with the customer. The
supplier has to action it, a tracking number has to appear and start moving,
and somebody has to tell the customer before they ask. The portal gathers each
order in one place, drafts the message to the supplier and the message to the
customer, and a person rates those drafts Accurate or Inaccurate so they get
better.
"""
import datetime as dt
import json
import os
import random

SEED = 20261022
AS_OF = dt.date(2026, 10, 22)
rng = random.Random(SEED)

STORES = ["Rosewood Home", "Trailhead Outdoors", "Petal & Pine"]
SUPPLIERS = ["Linfield Supply", "Kestrel Goods"]
CARRIERS = ["Royal Mail", "USPS", "Evri", "DHL eCommerce", "Canada Post"]

STATES = [
    ("Awaiting supplier", 0.22, "Supplier has not actioned the order yet."),
    ("In production",     0.18, "Supplier has accepted it, nothing has shipped."),
    ("Tracking issued",   0.16, "A tracking number exists but has not scanned."),
    ("In transit",        0.24, "Moving, last scan is recent."),
    ("Stalled",           0.12, "Tracking has not updated in over a week."),
    ("Exception",         0.08, "Carrier has reported a problem."),
]

FIRST = ["Amelia","Noah","Priya","Luca","Maeve","Theo","Isla","Hugo","Rosa","Elliot",
         "Nadia","Caleb","Freya","Omar","Sofia","Dylan","Marta","Jonah","Lena","Felix",
         "Ruth","Arlo","Nina","Beatriz","Samir","Clara","Victor","Imogen","Dara","Pablo"]
LAST  = ["Whitfield","Ortega","Nakamura","Bergstrom","Oyelaran","Castellanos","Lindqvist",
         "Varga","Mbeki","Ferreira","Donnelly","Kaur","Ivanova","Okafor","Rahman","Costa",
         "Lindgren","Brennan","Salazar","Petrov"]
STREETS = ["Ashgrove Lane","Kingfisher Way","Marlowe Street","Bramble Court","Pennant Road",
           "Halliwell Drive","Sycamore Rise","Fennel Close","Barrow Hill","Cobden Terrace"]
CITIES = [("Leeds","LS6 3AQ","United Kingdom"),("Portland","97212","United States"),
          ("Bristol","BS7 8RT","United Kingdom"),("Austin","78704","United States"),
          ("Calgary","T2N 1N4","Canada"),("Manchester","M20 2RN","United Kingdom"),
          ("Denver","80206","United States"),("Ottawa","K1N 7B5","Canada")]

PRODUCTS = {
 "Rosewood Home": [("Linen Wave Duvet Set","RH-1042"),("Stoneware Mug, Set of 4","RH-2218"),
   ("Ribbed Glass Carafe","RH-3301"),("Oak Bedside Tray","RH-1877"),("Waffle Cotton Throw","RH-2605")],
 "Trailhead Outdoors": [("Packable Down Vest","TO-5510"),("Dry Bag 20L","TO-4420"),
   ("Trail Running Belt","TO-6102"),("Insulated Flask 750ml","TO-3388"),("Merino Crew Socks","TO-2041")],
 "Petal & Pine": [("Dried Stem Bundle","PP-7701"),("Ceramic Planter, Medium","PP-6620"),
   ("Brass Plant Mister","PP-8140"),("Seed Starter Kit","PP-5533"),("Hanging Rattan Basket","PP-9012")],
}

def nice(d):
    """2026-10-04 -> 4 Oct 2026, so the drafts read like a person wrote them."""
    if not d: return ""
    if isinstance(d, str): d = dt.date.fromisoformat(d)
    return f"{d.day} {d.strftime('%b')} {d.year}"

def money(lo, hi):
    return round(rng.uniform(lo, hi), 2)

def pick_state():
    r, acc = rng.random(), 0.0
    for name, w, blurb in STATES:
        acc += w
        if r <= acc:
            return name, blurb
    return STATES[-1][0], STATES[-1][2]

def tracking_for(carrier):
    if carrier == "Royal Mail":  return "RM" + "".join(rng.choice("0123456789") for _ in range(9)) + "GB"
    if carrier == "USPS":        return "94" + "".join(rng.choice("0123456789") for _ in range(20))
    if carrier == "Evri":        return "H00" + "".join(rng.choice("0123456789") for _ in range(13))
    if carrier == "Canada Post": return "".join(rng.choice("0123456789") for _ in range(16))
    return "GM" + "".join(rng.choice("0123456789") for _ in range(14))

def draft_supplier(o):
    if o["state"] == "Awaiting supplier":
        return (f'Hi {o["supplier"]} team,\n\nOrder {o["order"]} ({o["product"]} x{o["qty"]}) was paid on '
                f'{nice(o["date"])} and has not been actioned yet. Please confirm today whether it is in stock '
                f'and when it will be despatched.\n\nIf it is out of stock, say so now and I will arrange '
                f'a replacement with the customer rather than let it sit.\n\nThanks,\nOperations')
    if o["state"] == "In production":
        return (f'Hi {o["supplier"]} team,\n\nOrder {o["order"]} ({o["product"]} x{o["qty"]}) has been with you '
                f'since {nice(o["date"])}. Could you confirm the despatch date and send the tracking number as soon '
                f'as it is generated?\n\nThanks,\nOperations')
    if o["state"] == "Tracking issued":
        return (f'Hi {o["supplier"]} team,\n\nTracking {o["tracking"]} was issued for order {o["order"]} but '
                f'has not scanned with {o["carrier"]} yet. Please confirm the parcel has physically been handed '
                f'over, not just labelled.\n\nThanks,\nOperations')
    if o["state"] == "Stalled":
        return (f'Hi {o["supplier"]} team,\n\nTracking {o["tracking"]} for order {o["order"]} has not updated '
                f'since {nice(o["last_scan"])}. Please open a trace with {o["carrier"]} and tell me whether to expect '
                f'movement or to send a replacement.\n\nThanks,\nOperations')
    if o["state"] == "Exception":
        return (f'Hi {o["supplier"]} team,\n\n{o["carrier"]} has flagged a problem on tracking {o["tracking"]} '
                f'for order {o["order"]}: {o["exception"]}. Please confirm whether the parcel can be recovered '
                f'or whether we should send a replacement from stock.\n\nThanks,\nOperations')
    return (f'Hi {o["supplier"]} team,\n\nOrder {o["order"]} is moving normally on {o["tracking"]}. No action '
            f'needed, logging it here so the trail is complete.\n\nThanks,\nOperations')

def draft_customer(o):
    first = o["customer"].split()[0]
    if o["state"] in ("Awaiting supplier", "In production"):
        return (f'Hi {first},\n\nThank you for your order of the {o["product"]}. It is being prepared now and '
                f'I am chasing the despatch date today. I will send your tracking number the moment it is '
                f'issued, and you do not need to do anything in the meantime.\n\nBest wishes,\nCustomer Care')
    if o["state"] == "Tracking issued":
        return (f'Hi {first},\n\nGood news, your {o["product"]} has been labelled for despatch and your tracking '
                f'number is {o["tracking"]}. It can take a day or two before the first scan appears, so do not '
                f'worry if it looks quiet at first.\n\nBest wishes,\nCustomer Care')
    if o["state"] == "In transit":
        return (f'Hi {first},\n\nYour {o["product"]} is on its way with {o["carrier"]}, tracking {o["tracking"]}. '
                f'The latest scan was on {nice(o["last_scan"])} and it is moving as expected.\n\nBest wishes,\nCustomer Care')
    if o["state"] == "Stalled":
        return (f'Hi {first},\n\nI am writing before you have to ask. Your {o["product"]} is tracked as '
                f'{o["tracking"]} and the last scan was {nice(o["last_scan"])}, which is longer than I am comfortable '
                f'with. I have asked {o["carrier"]} to trace it and I will come back to you by the end of the '
                f'week with either movement or a replacement on its way.\n\nBest wishes,\nCustomer Care')
    return (f'Hi {first},\n\nI am sorry, there has been a problem with your {o["product"]}: {o["exception"]}. '
            f'I am arranging a replacement now rather than waiting for the parcel to turn up. I will confirm '
            f'the new despatch today.\n\nBest wishes,\nCustomer Care')

EXCEPTIONS = ["address incomplete at the depot","parcel damaged in transit","held at customs for paperwork",
              "delivery refused at the address","returned to sender by the carrier"]
TAGS = ["VIP","Repeat customer","Gift order","Replacement","First order"]

orders = []
for n in range(78):
    store = rng.choice(STORES)
    product, sku = rng.choice(PRODUCTS[store])
    state, blurb = pick_state()
    placed = AS_OF - dt.timedelta(days=rng.randint(3, 44))
    carrier = rng.choice(CARRIERS)
    qty = rng.choices([1,1,1,2,2,3], k=1)[0]
    city, postcode, country = rng.choice(CITIES)
    cust = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    has_tracking = state in ("Tracking issued","In transit","Stalled","Exception")
    last_scan = None
    if state == "In transit":   last_scan = AS_OF - dt.timedelta(days=rng.randint(0, 3))
    elif state == "Stalled":    last_scan = AS_OF - dt.timedelta(days=rng.randint(9, 21))
    elif state == "Exception":  last_scan = AS_OF - dt.timedelta(days=rng.randint(2, 10))
    o = {
        "order": f"#{rng.randint(10000, 99999)}",
        "store": store, "product": product, "sku": sku, "qty": qty,
        "customer": cust,
        "email": cust.lower().replace(" ", ".") + "@example.com",
        "address": f'{rng.randint(1,180)} {rng.choice(STREETS)}, {city} {postcode}, {country}',
        "country": country,
        "date": placed.isoformat(),
        "age_days": (AS_OF - placed).days,
        "total": money(18, 240),
        "supplier": rng.choice(SUPPLIERS),
        "state": state, "state_note": blurb,
        "carrier": carrier if has_tracking else None,
        "tracking": tracking_for(carrier) if has_tracking else None,
        "last_scan": last_scan.isoformat() if last_scan else None,
        "exception": rng.choice(EXCEPTIONS) if state == "Exception" else None,
        "tags": rng.sample(TAGS, rng.choice([0,0,1,1,2])),
        "customer_asked": rng.random() < 0.28,
        "informed": rng.random() < 0.45,
    }
    o["draft_supplier"] = draft_supplier(o)
    o["draft_customer"] = draft_customer(o)
    orders.append(o)

orders.sort(key=lambda o: (-o["age_days"], o["order"]))
payload = {"as_of": AS_OF.isoformat(), "stores": STORES, "suppliers": SUPPLIERS,
           "states": [s[0] for s in STATES], "orders": orders}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.js")
with open(out, "w", encoding="utf-8") as f:
    f.write("const DEMO = " + json.dumps(payload, separators=(",", ":")) + ";\n")
print(f"wrote {out}: {len(orders)} orders")
