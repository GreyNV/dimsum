"""Encounter, drop and chain map for Dimensional Summoner, generated from the live catalog.

Usage: python tools/encounter_map.py "Claude outputs/encounter_map.xlsx"
Formulas have no cached values until recalculated (open in Excel/LibreOffice, or run a
LibreOffice headless recalc). Needs openpyxl.
"""
import sys
from pathlib import Path
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter as L

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dimensional_sim.world.catalog import (ACTIONS, DROP_TABLES, ITEMS, RARITY, REGIONS, TIER_ODDS_CAP,  # noqa
                                           UNLOCKS, BIOMES, SITES, SITE_CELL, BUILDINGS,
                                           ENEMIES, REGION_CELL, ECOLOGY, SITE_CONDITIONS, BY_ID)
from dimensional_sim.world.tuning import (CARRY_FREE, CARRY_MAX_PERCENT, CARRY_PERCENT_PER_ITEM,  # noqa
                                          CHEST_SLOTS, STOW_TRIP_AT)
from dimensional_sim.world.tuning import PRESSURE_FLOOR, PRESSURE_STEP, SHIMMER_RARITY_PERCENT, SPOTS_PER_CHUNK

OUT = sys.argv[1]
F = "Arial"
BLUE = Font(name=F, color="0000FF")
BLACK = Font(name=F)
BOLD = Font(name=F, bold=True)
HEAD = Font(name=F, bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", start_color="2F4F3A")
SUB_FILL = PatternFill("solid", start_color="E8EFE6")
INPUT_FILL = PatternFill("solid", start_color="FFF7D6")
TITLE = Font(name=F, bold=True, size=14)
NOTE = Font(name=F, italic=True, color="555555", size=9)
PCT = "0.0%"
PCT2 = "0.00%"
TIER_FILL = {"common": None, "uncommon": PatternFill("solid", start_color="E3F4DC"),
             "rare": PatternFill("solid", start_color="DCE8FA")}

wb = Workbook()


def header(ws, row, cols, start=1):
    for i, text in enumerate(cols):
        c = ws.cell(row=row, column=start + i, value=text)
        c.font, c.fill = HEAD, HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[row].height = 32


def put(ws, row, col, value, font=BLACK, fmt=None, fill=None):
    c = ws.cell(row=row, column=col, value=value)
    c.font = font
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    return c


def inp(ws, row, col, value, fmt=None):
    return put(ws, row, col, value, BLUE, fmt, INPUT_FILL)


def widths(ws, values):
    for i, w in enumerate(values, 1):
        ws.column_dimensions[L(i)].width = w


def title(ws, text, sub):
    put(ws, 1, 1, text, TITLE)
    put(ws, 2, 1, sub, NOTE)


SPOTS = [a for a in ACTIONS if a.placement == "spot"]
LEADS = [a for a in ACTIONS if a.placement == "lead"]
SITE_ACTIONS = [a for a in ACTIONS if a.placement == "site"]
ENC = SPOTS + LEADS
REG = list(REGIONS.values())
TIERS = ["rare", "uncommon", "common"]

# ---------------------------------------------------------------- Read me
ws = wb.active
ws.title = "Read me"
title(ws, "Dimensional Summoner — encounters, drops and chains",
      "Generated from src/dimensional_sim/world/catalog.py on 2026-10-16 (6 landmark sites, camp buildings; encounters-v11, save schema 13).")
rows = [
    ("How to use", ""),
    ("Blue text on yellow", "An input you can change: weights, region %, tier odds, drop odds, chances."),
    ("Black text", "A formula. Every chance in this workbook recalculates from the inputs."),
    ("Changing the game", "Edits here do not change the game. Send the file back and the changes get ported into catalog.py."),
    ("", ""),
    ("How a spot is rolled", ""),
    ("1. Spots per chunk", f"Each new chunk rolls one entry of {list(SPOTS_PER_CHUNK)} (average {sum(SPOTS_PER_CHUNK)/len(SPOTS_PER_CHUNK):.1f} spots)."),
    ("2. Tier first", "Rare rolls first; a miss tries uncommon; common catches the rest. A tier with nothing eligible is skipped."),
    ("3. Tier odds scale", "Tier odds x (eligible weight in that tier / its full weight), capped at 90%. Unlocking more of a tier raises its odds."),
    ("4. Pick in tier", "Inside the tier, an encounter is picked by effective weight (base weight x region %, rounded down like the game)."),
    ("5. After the roll", "At-once caps (windows), spawn pity and the Journal guarantee apply after this table; Journal favor/suppress is not modelled here."),
    ("", ""),
    ("How loot works", ""),
    ("Fixed loot", "Each fixed entry rolls on its own (sheet 'Fixed loot'). These feed the auto-pilot's food and crafting plans."),
    ("Bonus roll", "Actions with a drop table make ONE extra cascading roll (sheet 'Drop tables'); at most one item. Ring depth does not apply."),
    ("", ""),
    ("Chains", "Completing an encounter can create a temporary lead next to it (sheet 'Chains'). Leads are not part of the spawn roll."),
    ("Sites", "A site's own encounters are drawn from its bucket by base weight (region % does not apply), each at most once, on top of the wild spots."),
    ("", ""),
    ("Sheets", ""),
    ("Encounters", "Every spot and lead: tier, weight, unlock, regions, caps, fight HP, drops."),
    ("Spawn odds", "Chance per spot draw in each region, with an 'Unlocked' switch per encounter."),
    ("Regions", "Region weight % per encounter (0 = never there)."),
    ("Tiers", "Tier odds and full weights for encounter spots."),
    ("Fixed loot", "Guaranteed/independent drops per action."),
    ("Drop tables", "Bonus-roll tables, tier odds, picks, and each item's exact chance per table."),
    ("Bonus drops", "Each action's bonus items with chance and expected ash per completion."),
    ("Chains", "Current chained encounters plus a blank table for chain ideas."),
    ("Sites", "Landmark sites: where they can appear, how often, and their own encounters."),
    ("Site encounters", "Inside each site: how likely each of its encounters is to show up in a life, and what it gives."),
    ("Biomes & enemies", "Biomes, region layout (canopy, brush, which sites can appear) and enemy danger by ring."),
    ("Crafts & buildings", "Every craft and building: where it can be made, cost, result, gate and bind cost."),
    ("Carry load", "How carried items slow walking, eased by Endurance and Strength."),
    ("Items", "Every item: kind, rarity, food, ash value."),
    ("Exhaustion", "How harvesting thins out an area for the rest of the life, per kind of resource."),
    ("Site conditions", "How a landmark is this life (quiet, already searched, untouched, a den, overgrown) and the rare phenomena."),
]
for i, (k, v) in enumerate(rows, start=4):
    put(ws, i, 1, k, BOLD if not v else BLACK)
    put(ws, i, 2, v)
put(ws, 4, 1, "How to use", BOLD)
widths(ws, [24, 120])

# ---------------------------------------------------------------- Tiers
tw = wb.create_sheet("Tiers")
title(tw, "Encounter tier odds", "Basis points in the catalog; shown here as %. The fallback tier (common) has no odds: it catches misses.")
header(tw, 4, ["Tier", "Spot odds", "Full weight", "Color", "Notes"])
TIER_ROW = {}
for i, t in enumerate(TIERS):
    r = 5 + i
    d = RARITY[t]
    TIER_ROW[t] = r
    put(tw, r, 1, t)
    if t == "common":
        put(tw, r, 2, "fallback", NOTE)
        put(tw, r, 3, "-", NOTE)
    else:
        inp(tw, r, 2, d.spot_odds / 10000, PCT)
        inp(tw, r, 3, d.spot_full_weight)
    put(tw, r, 4, d.color)
    put(tw, r, 5, {"rare": "No rare encounters exist yet: the tier is skipped.",
                   "uncommon": "Full odds once this much uncommon weight is eligible here.",
                   "common": ""}[t], NOTE)
put(tw, 9, 1, "Tier cap", BOLD)
inp(tw, 9, 2, TIER_ODDS_CAP / 10000, PCT)
put(tw, 10, 1, "Ring (depth)", BOLD)
inp(tw, 10, 2, 0)
put(tw, 10, 3, "ring of the chunk being rolled", NOTE)
put(tw, 11, 1, "Rarity per ring", BOLD)
inp(tw, 11, 2, BIOMES["dark_forest"].spot_rarity_per_ring / 100, PCT)
put(tw, 11, 3, "dark_forest.spot_rarity_per_ring (0 = depth does not change odds)", NOTE)
put(tw, 12, 1, "Ring multiplier", BOLD)
put(tw, 12, 2, "=1+B11*B10", BLACK, "0.00")
widths(tw, [18, 12, 12, 10, 60])
CAP, RINGM = "Tiers!$B$9", "Tiers!$B$12"

# ---------------------------------------------------------------- Encounters
ew = wb.create_sheet("Encounters")
title(ew, "Encounters", "Spots are rolled into chunks; leads only appear through a chain (see Chains); site encounters only inside their landmark (see Sites).")
cols = ["ID", "Name", "Placement", "Category", "Tier", "Base weight", "Unlock (cost)", "Needs knowledge",
        "Allowed regions", "Next to", "At-once cap", "Enemy HP", "XP", "Duration (s)", "Heal", "(unused)",
        "Bonus table", "Leads to", "Interaction (what you do)", "Depletes nearby"]
header(ew, 4, cols)
ENC_ROW = {}
for i, a in enumerate(ENC + SITE_ACTIONS):
    r = 5 + i
    ENC_ROW[a.id] = r
    u = UNLOCKS.get(a.unlock) if a.unlock else None
    vals = [a.id, a.name, a.placement, a.category, a.rarity, None,
            (f"{u.name} ({u.level[0]} {u.level[1]})" if u.level else f"{u.name} ({u.cost} {u.currency})") if u else "start",
            a.knowledge or "", SITES[a.site].name if a.site else
            ", ".join(REGIONS[x].name for x in a.regions) if a.regions else "all",
            {"T": "tree", "^": "rock"}.get(a.near, ""),
            f"{a.window[0]}-{a.window[1]}" if a.window else "no cap", a.hp or "", a.xp,
            a.duration_ms / 1000, a.heal or "", "", a.drops or "",
            ", ".join(f"{o.id} ({o.chance}%)" for o in a.outcomes if o.kind == "lead"), a.interaction or "", a.ecology or ""]
    for j, v in enumerate(vals, 1):
        put(ew, r, j, v, fill=TIER_FILL[a.rarity])
    if a.placement in ("spot", "site"):
        inp(ew, r, 6, a.weight)
    else:
        put(ew, r, 6, "lead", NOTE)
ew.freeze_panes = "C5"
widths(ew, [20, 20, 10, 10, 10, 10, 26, 14, 34, 8, 10, 8, 6, 10, 6, 8, 16, 26, 28, 14])

# ---------------------------------------------------------------- Sites
sw = wb.create_sheet("Sites")
title(sw, "Landmark sites", f"One candidate chunk per {SITE_CELL}x{SITE_CELL} block rolls once against these per-mille weights (by its region).")
header(sw, 4, ["Site", "Structure", "Min ring", "Encounters per life"] + [f"Chance · {r.name}" for r in REG]
       + ["Its encounters"])
for i, site in enumerate(SITES.values()):
    r = 5 + i
    put(sw, r, 1, site.name)
    put(sw, r, 2, site.structure)
    inp(sw, r, 3, site.min_ring)
    put(sw, r, 4, f"{site.spots[0]}-{site.spots[1]}")
    for j, reg in enumerate(REG):
        inp(sw, r, 5 + j, site.weights.get(reg.id, 0) / 1000, "0.0%")
    put(sw, r, 5 + len(REG), ", ".join(a.name for a in SITE_ACTIONS if a.site == site.id))
n_sites = len(SITES)
put(sw, 6 + n_sites, 1, "Chance a block holds a site", BOLD)
for j in range(len(REG)):
    col = L(5 + j)
    put(sw, 6 + n_sites, 5 + j, f"=SUM({col}5:{col}{4 + n_sites})", BOLD, "0.0%")
put(sw, 7 + n_sites, 1, "Roughly one site per this many chunks", BOLD)
for j in range(len(REG)):
    col = L(5 + j)
    put(sw, 7 + n_sites, 5 + j, f"=IF({col}{6 + n_sites}=0,\"-\",{SITE_CELL * SITE_CELL}/{col}{6 + n_sites})", BOLD, "0")
widths(sw, [20, 10, 9, 12] + [16] * len(REG) + [60])

# ---------------------------------------------------------------- Regions
rw = wb.create_sheet("Regions")
title(rw, "Region weight %", "100 = unchanged, 0 = never here (includes 'Allowed regions'). Leads use this % on their lead chance.")
header(rw, 4, ["ID", "Name"] + [r.name for r in REG])
REG_ROW = {}
for i, a in enumerate(ENC):
    r = 5 + i
    REG_ROW[a.id] = r
    put(rw, r, 1, a.id)
    put(rw, r, 2, a.name)
    for j, reg in enumerate(REG):
        allowed = a.regions is None or reg.id in a.regions or a.placement == "lead"
        inp(rw, r, 3 + j, (reg.multiplier(a.id) if allowed else 0) / 100, "0%")
rw.freeze_panes = "C5"
widths(rw, [20, 22] + [16] * len(REG))

# ---------------------------------------------------------------- Spawn odds
so = wb.create_sheet("Spawn odds")
title(so, "Chance per spot draw, by region", "Set 'Unlocked' to 0 to model an earlier life. Chances are per spot; a chunk rolls about 1.5 spots.")
n = len(SPOTS)
first, last = 6, 6 + n - 1
put(so, 4, 1, "Encounter", BOLD)
for j, reg in enumerate(REG):
    c = 5 + j * 2
    so.merge_cells(start_row=4, start_column=c, end_row=4, end_column=c + 1)
    put(so, 4, c, reg.name, BOLD).alignment = Alignment(horizontal="center")
header(so, 5, ["ID", "Tier", "Unlocked", "Base weight"] + ["Eff. weight", "Chance"] * len(REG))
for i, a in enumerate(SPOTS):
    r = first + i
    put(so, r, 1, a.id, fill=TIER_FILL[a.rarity])
    put(so, r, 2, f"=Encounters!E{ENC_ROW[a.id]}", fill=TIER_FILL[a.rarity])
    inp(so, r, 3, 1)
    put(so, r, 4, f"=Encounters!F{ENC_ROW[a.id]}")
sum_row = last + 2
put(so, sum_row, 1, "Tier summary", BOLD)
lab = {"wR": "Eligible weight · rare", "wU": "Eligible weight · uncommon", "wC": "Eligible weight · common",
       "oR": "Tier odds · rare", "oU": "Tier odds · uncommon",
       "pR": "P(spot is rare)", "pU": "P(spot is uncommon)", "pC": "P(spot is common)", "chk": "Check: chances sum"}
keys = list(lab)
SR = {k: sum_row + 1 + i for i, k in enumerate(keys)}
for k in keys:
    put(so, SR[k], 1, lab[k], BOLD if k.startswith("p") else BLACK)
for j, reg in enumerate(REG):
    ew_c, ch_c = L(5 + j * 2), L(6 + j * 2)
    E = f"${ew_c}${first}:${ew_c}${last}"
    T = f"$B${first}:$B${last}"
    for i, a in enumerate(SPOTS):
        r = first + i
        put(so, r, 5 + j * 2, f"=INT($C{r}*$D{r}*Regions!{L(3 + j)}{REG_ROW[a.id]})", fmt="0")
        put(so, r, 6 + j * 2,
            f'=IF({ew_c}{r}=0,0,IF($B{r}="rare",{ch_c}${SR["pR"]}/{ew_c}${SR["wR"]},'
            f'IF($B{r}="uncommon",{ch_c}${SR["pU"]}/{ew_c}${SR["wU"]},{ch_c}${SR["pC"]}/{ew_c}${SR["wC"]}))*{ew_c}{r})',
            fmt=PCT)
    c = ew_c
    put(so, SR["wR"], 5 + j * 2, f'=SUMIFS({E},{T},"rare")', fmt="0.0")
    put(so, SR["wU"], 5 + j * 2, f'=SUMIFS({E},{T},"uncommon")', fmt="0.0")
    put(so, SR["wC"], 5 + j * 2, f'=SUMIFS({E},{T},"common")', fmt="0.0")
    put(so, SR["oR"], 6 + j * 2, f"=IF({c}{SR['wR']}=0,0,MIN({CAP},Tiers!$B${TIER_ROW['rare']}*{c}{SR['wR']}/Tiers!$C${TIER_ROW['rare']}*{RINGM}))", fmt=PCT)
    put(so, SR["oU"], 6 + j * 2, f"=IF({c}{SR['wU']}=0,0,MIN({CAP},Tiers!$B${TIER_ROW['uncommon']}*{c}{SR['wU']}/Tiers!$C${TIER_ROW['uncommon']}*{RINGM}))", fmt=PCT)
    h = ch_c
    put(so, SR["pR"], 6 + j * 2, f"=IF({c}{SR['wR']}=0,0,IF({c}{SR['wU']}+{c}{SR['wC']}=0,1,{h}{SR['oR']}))", BOLD, PCT)
    put(so, SR["pU"], 6 + j * 2, f"=IF({c}{SR['wU']}=0,0,IF({c}{SR['wC']}=0,1-{h}{SR['pR']},(1-{h}{SR['pR']})*{h}{SR['oU']}))", BOLD, PCT)
    put(so, SR["pC"], 6 + j * 2, f"=IF({c}{SR['wC']}=0,0,1-{h}{SR['pR']}-{h}{SR['pU']})", BOLD, PCT)
    put(so, SR["chk"], 6 + j * 2, f"=SUM(${h}${first}:${h}${last})", NOTE, PCT)
put(so, SR["chk"] + 2, 1, "The engine works in whole basis points, so in-game numbers can differ by about 0.1%.", NOTE)
so.freeze_panes = "E6"
widths(so, [20, 10, 9, 8] + [10, 10] * len(REG))

# ---------------------------------------------------------------- Fixed loot
fl = wb.create_sheet("Fixed loot")
title(fl, "Fixed loot", "Each row rolls on its own every completion. Expected = chance x average amount.")
header(fl, 4, ["Action", "Item", "Min", "Max", "Chance", "Expected per completion", "Ash per unit", "Expected ash"])
r = 5
for a in ACTIONS:
    for lo in a.loot:
        put(fl, r, 1, a.id)
        put(fl, r, 2, lo.item)
        inp(fl, r, 3, lo.low)
        inp(fl, r, 4, lo.high)
        inp(fl, r, 5, lo.chance / 100, "0%")
        put(fl, r, 6, f"=E{r}*(C{r}+D{r})/2", fmt="0.00")
        put(fl, r, 7, f"=INDEX(Items!$F:$F,MATCH(B{r},Items!$A:$A,0))")
        put(fl, r, 8, f"=F{r}*G{r}", fmt="0.00")
        r += 1
fl.freeze_panes = "A5"
widths(fl, [20, 18, 6, 6, 9, 14, 10, 12])

# ---------------------------------------------------------------- Drop tables
dt = wb.create_sheet("Drop tables")
title(dt, "Bonus drop tables", "One cascading roll: rare first, then uncommon, else common (an empty common pool means nothing drops).")
tables = list(DROP_TABLES.values())
header(dt, 4, ["Table", "Rare odds", "Uncommon odds", "Has rare pool", "Has uncommon pool", "Has common pool",
               "P(rare)", "P(uncommon)", "P(common)", "P(nothing)"])
TROW = {}
pick_first = 6 + len(tables) + 3
picks = [(t.id, tier, p) for t in tables for tier in TIERS for p in t.pools.get(tier, ())]
pick_last = pick_first + len(picks) - 1
PT, PTi, PP, PW, PD = (f"$A${pick_first}:$A${pick_last}", f"$B${pick_first}:$B${pick_last}",
                       f"$C${pick_first}:$C${pick_last}", f"$D${pick_first}:$D${pick_last}",
                       f"$I${pick_first}:$I${pick_last}")
for i, t in enumerate(tables):
    r = 5 + i
    TROW[t.id] = r
    put(dt, r, 1, t.id)
    for col, tier in ((2, "rare"), (3, "uncommon")):
        if tier in t.odds:
            inp(dt, r, col, t.odds[tier] / 10000, PCT)
        else:
            inp(dt, r, col, 0, PCT)
    for col, tier in ((4, "rare"), (5, "uncommon"), (6, "common")):
        put(dt, r, col, f'=IF(COUNTIFS({PT},$A{r},{PTi},"{tier}")>0,1,0)')
    put(dt, r, 7, f"=IF(D{r}=1,MIN(B{r},Tiers!$B$9),0)", fmt=PCT2)
    put(dt, r, 8, f"=IF(E{r}=1,(1-G{r})*MIN(C{r},Tiers!$B$9),0)", fmt=PCT2)
    put(dt, r, 9, f"=IF(F{r}=1,1-G{r}-H{r},0)", fmt=PCT2)
    put(dt, r, 10, f"=1-G{r}-H{r}-I{r}", fmt=PCT2)
put(dt, pick_first - 2, 1, "Picks (one per tier pool entry; 'table:' rolls that whole table)", BOLD)
header(dt, pick_first - 1, ["Table", "Tier", "Pick", "Weight", "Min", "Max", "Share in pool", "P(tier)", "Chance from this table"])
for i, (tid, tier, p) in enumerate(picks):
    r = pick_first + i
    put(dt, r, 1, tid)
    put(dt, r, 2, tier, fill=TIER_FILL[tier])
    put(dt, r, 3, p.item if p.item else f"table:{p.table}")
    inp(dt, r, 4, p.weight)
    if p.item:
        inp(dt, r, 5, p.low)
        inp(dt, r, 6, p.high)
    else:
        put(dt, r, 5, "-", NOTE)
        put(dt, r, 6, "-", NOTE)
    put(dt, r, 7, f"=D{r}/SUMIFS({PW},{PT},A{r},{PTi},B{r})", fmt=PCT)
    tcol = {"rare": "G", "uncommon": "H", "common": "I"}[tier]
    put(dt, r, 8, f"=INDEX(${tcol}$5:${tcol}${4 + len(tables)},MATCH(A{r},$A$5:$A${4 + len(tables)},0))", fmt=PCT2)
    put(dt, r, 9, f"=G{r}*H{r}", fmt=PCT2)


def flat(tid, seen=()):
    out = []
    for tier in TIERS:
        for p in DROP_TABLES[tid].pools.get(tier, ()):
            if p.item:
                if p.item not in out:
                    out.append(p.item)
            else:
                for it in flat(p.table):
                    if it not in out:
                        out.append(it)
    return out


def reachable_picks(tid, item):
    out = []
    for pool in DROP_TABLES[tid].pools.values():
        for p in pool:
            if p.item == item:
                out.append(p)
            elif p.table:
                out += reachable_picks(p.table, item)
    return out


def nested_order():
    done, order = set(), []

    def visit(tid):
        if tid in done:
            return
        for pool in DROP_TABLES[tid].pools.values():
            for p in pool:
                if p.table:
                    visit(p.table)
        done.add(tid)
        order.append(tid)
    for t in tables:
        visit(t.id)
    return order


ic_first = pick_last + 4
put(dt, ic_first - 2, 1, "Each item's chance per table roll (nested tables included)", BOLD)
header(dt, ic_first - 1, ["Table", "Item", "Chance per roll"])
IC = {}
r = ic_first
for tid in nested_order():
    for item in flat(tid):
        IC[(tid, item)] = r
        put(dt, r, 1, tid)
        put(dt, r, 2, item)
        terms = [f'SUMIFS({PD},{PT},A{r},{PP},B{r})']
        for pool in DROP_TABLES[tid].pools.values():
            for p in pool:
                if p.table and (p.table, item) in IC:
                    terms.append(f'SUMIFS({PD},{PT},A{r},{PP},"table:{p.table}")*C{IC[(p.table, item)]}')
        put(dt, r, 3, "=" + "+".join(terms), fmt=PCT2)
        r += 1
ic_last = r - 1
dt.freeze_panes = "B5"
widths(dt, [18, 12, 22, 10, 10, 10, 12, 12, 14, 12])

# ---------------------------------------------------------------- Bonus drops
bd = wb.create_sheet("Bonus drops")
title(bd, "Bonus drops by action", "One bonus roll per completion. Chance comes from the 'Drop tables' sheet.")
header(bd, 4, ["Action", "Table", "Item", "Item rarity", "Chance per completion", "Ash per unit", "Avg amount",
               "Expected ash per completion"])
r = 5
for a in ACTIONS:
    if not a.drops:
        continue
    for item in flat(a.drops):
        put(bd, r, 1, a.id)
        put(bd, r, 2, a.drops)
        put(bd, r, 3, item)
        put(bd, r, 4, f"=INDEX(Items!$D:$D,MATCH(C{r},Items!$A:$A,0))", fill=TIER_FILL[ITEMS[item].rarity])
        put(bd, r, 5, f"=SUMIFS('Drop tables'!$C${ic_first}:$C${ic_last},'Drop tables'!$A${ic_first}:$A${ic_last},B{r},"
                      f"'Drop tables'!$B${ic_first}:$B${ic_last},C{r})", fmt=PCT2)
        put(bd, r, 6, f"=INDEX(Items!$F:$F,MATCH(C{r},Items!$A:$A,0))")
        lo = reachable_picks(a.drops, item)
        put(bd, r, 7, sum((p.low + p.high) / 2 for p in lo) / len(lo), NOTE, "0.0")
        if len({(p.low, p.high) for p in lo}) > 1:
            bd.cell(row=r, column=7).comment = Comment("Amount differs between the picks that can give it; this is their plain average.", "Claude")
        put(bd, r, 8, f"=E{r}*F{r}*G{r}", fmt="0.00")
        r += 1
bd.freeze_panes = "A5"
widths(bd, [20, 16, 16, 12, 14, 10, 10, 14])

# ---------------------------------------------------------------- Chains
cw = wb.create_sheet("Chains")
title(cw, "Chained encounters", "What completing an encounter can unlock or spawn next. Leads appear next to their source and expire.")
header(cw, 4, ["Source", "Outcome", "Target", "From completion #", "Base chance", "Lifetime (s)"]
       + [f"Chance · {reg.name}" for reg in REG] + ["Chain from start (base)"])
r = 5
CH = {}
for a in ACTIONS:
    for o in a.outcomes:
        CH[(a.id, o.id)] = r
        put(cw, r, 1, a.id)
        put(cw, r, 2, o.kind)
        put(cw, r, 3, o.id)
        inp(cw, r, 4, o.at_count)
        inp(cw, r, 5, o.chance / 100, "0%")
        put(cw, r, 6, o.ttl_ms / 1000 if o.ttl_ms else "-")
        for j in range(len(REG)):
            if o.kind == "lead":
                put(cw, r, 7 + j, f"=MIN(1,E{r}*Regions!{L(3 + j)}{REG_ROW[o.id]})", fmt="0%")
            else:
                put(cw, r, 7 + j, f"=E{r}", fmt="0%")
        parent = next((CH[k] for k in CH if k[1] == a.id), None)
        put(cw, r, 7 + len(REG), f"=E{r}*{L(7 + len(REG))}{parent}" if parent else f"=E{r}", fmt="0%")
        if parent:
            cw.cell(row=r, column=7 + len(REG)).comment = Comment(
                "Base chance of reaching this step from the first encounter in the chain (regions ignored).", "Claude")
        r += 1
idea = r + 2
put(cw, idea, 1, "Chain ideas — fill in (one example row)", BOLD)
put(cw, idea + 1, 1, "Kinds: lead = temporary spot next to the source; shimmer = rare spots likelier in this region cell for the life; renew = lift that cell's exhaustion of one kind; boost = raise one target's odds nearby (proposed, not built yet).", NOTE)
header(cw, idea + 2, ["Source", "Kind", "Target", "From completion #", "Chance", "Lifetime (s)", "Boost x", "Radius (chunks)", "Why"])
example = ["abandoned_camp", "boost", "old_carvings", 1, 1.0, 120, 3, 1, "Travellers' camp hints at old marks nearby"]
for j, v in enumerate(example, 1):
    c = put(cw, idea + 3, j, v, NOTE, "0%" if j == 5 else None)
for rr in range(idea + 4, idea + 14):
    for j in range(1, 10):
        inp(cw, rr, j, None)
cw.freeze_panes = "B5"
widths(cw, [20, 10, 20, 10, 10, 10] + [14] * len(REG) + [14])

# ---------------------------------------------------------------- Crafts & buildings
cb = wb.create_sheet("Crafts & buildings")
title(cb, "Crafts and buildings", "Crafts and buildings are made at the anchor camp (crafts need a crafting station); "
      "buildings fall when the life ends unless bound with ash. A campfire is made anywhere, once hurt and far away.")
header(cb, 4, ["ID", "Name", "Kind", "Workplace", "Cost", "Result", "Gate", "Discipline", "XP",
               "Duration (s)", "Need order", "Bind cost (ash)"])
made = [a for a in ACTIONS if a.category in ("craft", "build", "camp")]
made.sort(key=lambda a: (a.category != "build", a.need_priority, a.id))
for i, a in enumerate(made):
    r = 5 + i
    gate = [f"knowledge {q.id}" for q in a.requirements if q.kind == "knowledge"]
    if a.recipe:
        gate.append(f"recipe {a.recipe} (" + ", ".join(b.name for b in ACTIONS for o in b.outcomes
                                                       if o.kind == "recipe" and o.id == a.recipe) + ")")
    if a.unlock:
        gate.append(f"unlock {UNLOCKS[a.unlock].name}")
    if a.need_flag:
        gate.append("when " + a.need_flag.replace("_", " "))
    result = (BUILDINGS[a.builds].name if a.builds else ITEMS[a.effect].name if a.effect else
              f"a {a.places} (rest by it like at the anchor camp)" if a.places else
              ", ".join(f"{ITEMS[l.item].name} {l.chance}%" for l in a.loot))
    workplace = ("anywhere" if a.workplace is None else "anchor camp" if a.workplace == "camp"
                 else f"{BUILDINGS[a.workplace].name} (camp)")
    vals = [a.id, a.name, a.category, workplace, ", ".join(f"{n} {ITEMS[i].name.lower()}" for i, n in a.cost),
            result, "; ".join(gate) or "-", a.attribute.capitalize(), a.xp, a.duration_ms / 1000, a.need_priority]
    for j, v in enumerate(vals, 1):
        put(cb, r, j, v)
    if a.builds:
        inp(cb, r, 12, BUILDINGS[a.builds].bind_cost)
    else:
        put(cb, r, 12, "-", NOTE)
br = 6 + len(made)
put(cb, br, 1, "Buildings", BOLD)
header(cb, br + 1, ["Building", "Function", "Bind cost (ash)", "What it does"])
for i, b in enumerate(BUILDINGS.values()):
    put(cb, br + 2 + i, 1, b.name)
    put(cb, br + 2 + i, 2, b.function)
    inp(cb, br + 2 + i, 3, b.bind_cost)
    put(cb, br + 2 + i, 4, b.description + (f" Holds {CHEST_SLOTS} stacks; the auto-pilot goes home to stow at "
                                             f"{STOW_TRIP_AT} carried materials." if b.function == "storage" else ""))
put(cb, br + 3 + len(BUILDINGS), 1, "'Need order': when several are possible, the lowest number is made first.", NOTE)
cb.freeze_panes = "C5"
widths(cb, [16, 26, 8, 16, 34, 22, 46, 12, 6, 11, 10, 14])

# ---------------------------------------------------------------- Carry load
cl = wb.create_sheet("Carry load")
title(cl, "Carry load", "Walking time in % of normal. Every carried unit beyond the free amount adds the per-item %, "
      "divided by the average Endurance/Strength speed, up to the cap.")
put(cl, 4, 1, "Free units", BOLD); inp(cl, 4, 2, CARRY_FREE)
put(cl, 5, 1, "+% per further unit", BOLD); inp(cl, 5, 2, CARRY_PERCENT_PER_ITEM)
put(cl, 6, 1, "Cap (+%)", BOLD); inp(cl, 6, 2, CARRY_MAX_PERCENT)
reliefs = (1.0, 1.25, 1.5, 2.0)
header(cl, 8, ["Carried units"] + [f"Walking time · End/Str speed x{f:.2f}" for f in reliefs])
for j, f in enumerate(reliefs):
    inp(cl, 9, 2 + j, f, "0.00")
put(cl, 9, 1, "speed (edit)", NOTE)
for i, n in enumerate(range(0, 101, 10)):
    r = 10 + i
    put(cl, r, 1, n)
    for j in range(len(reliefs)):
        c = L(2 + j)
        put(cl, r, 2 + j, f"=1+MIN($B$6,INT(MAX(0,$A{r}-$B$4)*$B$5/{c}$9))/100", fmt="0%")
put(cl, 22, 1, "The game rounds down to whole percents. A full pack (12 stacks of 20) is 240 units.", NOTE)
widths(cl, [20, 22, 22, 22, 22])


# ---------------------------------------------------------------- Site encounters
se = wb.create_sheet("Site encounters")
title(se, "Site encounters", "Each life a site draws 'Min-Max' of its encounters (count uniform), by weight, each at most once. "
      "Assumes all of them are unlocked; a locked one simply drops out of the draw.")
r = 4
for site in SITES.values():
    acts = [a for a in SITE_ACTIONS if a.site == site.id]
    put(se, r, 1, site.name, TITLE)
    put(se, r, 3, "Min", BOLD); inp(se, r, 4, site.spots[0])
    put(se, r, 5, "Max", BOLD); inp(se, r, 6, site.spots[1])
    put(se, r, 7, f"structure: {site.structure} · min ring {site.min_ring} · {site.rarity}", NOTE)
    lo, hi = f"$D${r}", f"$F${r}"
    header(se, r + 1, ["ID", "Name", "Weight (Encounters sheet)", "P(1st pick)", "P(2nd pick)", "P(3rd pick)",
                       "P(4th pick)", "P(shows up in a life)", "Unlock", "Fixed loot", "Bonus table", "Other"])
    first = r + 2
    rows = list(range(first, first + len(acts)))
    W = {a.id: f"$C${rr}" for a, rr in zip(acts, rows)}
    tot = f"SUM($C${first}:$C${rows[-1]})"
    for a, rr in zip(acts, rows):
        put(se, rr, 1, a.id); put(se, rr, 2, a.name)
        put(se, rr, 3, f"=Encounters!F{ENC_ROW[a.id]}")
        me, others = W[a.id], [W[b.id] for b in acts if b is not a]
        p1 = f"{me}/{tot}"
        p2 = "+".join(f"({j}/{tot})*({me}/({tot}-{j}))" for j in others) or "0"
        p3 = "+".join(f"({j}/{tot})*({k}/({tot}-{j}))*({me}/({tot}-{j}-{k}))"
                      for j in others for k in others if k != j) or "0"
        p4 = "+".join(f"({j}/{tot})*({k}/({tot}-{j}))*({m}/({tot}-{j}-{k}))*({me}/({tot}-{j}-{k}-{m}))"
                      for j in others for k in others for m in others if len({j, k, m}) == 3) or "0"
        for c, f in ((4, p1), (5, p2), (6, p3), (7, p4)):
            put(se, rr, c, f"={f}", fmt=PCT)
        # appears = average over counts lo..hi of P(in first c picks)
        cum = lambda c: "+".join(f"{L(4 + i)}{rr}" for i in range(c)) if c else "0"
        terms = [f"IF(AND({c}>={lo},{c}<={hi}),{cum(min(c, 4))},0)" for c in range(0, 9)]
        put(se, rr, 8, f"=MIN(1,({'+'.join(terms)})/({hi}-{lo}+1))", BOLD, PCT)
        u = UNLOCKS.get(a.unlock) if a.unlock else None
        put(se, rr, 9, (f"{u.name} ({u.level[0]} {u.level[1]})" if u.level else f"{u.name} ({u.cost} {u.currency})") if u else "start")
        put(se, rr, 10, ", ".join(f"{ITEMS[x.item].name} {x.low}-{x.high}" + (f" ({x.chance}%)" if x.chance < 100 else "")
                                  for x in a.loot))
        put(se, rr, 11, a.drops or "")
        extra = [f"heal {a.heal}" if a.heal else "",
                 ", ".join(f"teaches {o.id}" for o in a.outcomes if o.kind == "recipe"),
                 f"{a.category} · {a.attribute} {a.xp} XP · {a.duration_ms / 1000:g}s"]
        put(se, rr, 12, " · ".join(x for x in extra if x))
    put(se, rows[-1] + 1, 2, "Check: picks per life", NOTE)
    put(se, rows[-1] + 1, 8, f"=SUM(H{first}:H{rows[-1]})", NOTE, "0.00")
    r = rows[-1] + 3
put(se, r, 1, "'Check' should equal the average of Min..Max (fewer if a site has fewer encounters than Max).", NOTE)
se.freeze_panes = "C4"
widths(se, [18, 20, 12, 10, 10, 10, 10, 14, 26, 40, 16, 60])

# ---------------------------------------------------------------- Biomes & enemies
be = wb.create_sheet("Biomes & enemies")
title(be, "Biomes, regions and enemies", f"Regions are {REGION_CELL}x{REGION_CELL}-chunk cells picked by weight "
      "(the anchor cell is always The Old Road). Danger grows with the ring (distance from the anchor, in chunks).")
header(be, 4, ["Biome", "Name", "Enemy hit growth / ring", "Enemy HP / ring", "Danger stops at ring",
               "Spot rarity / ring", "Status"])
BIO_ROW = {}
for i, b in enumerate(BIOMES.values()):
    rr = 5 + i
    BIO_ROW[b.id] = rr
    put(be, rr, 1, b.id); put(be, rr, 2, b.name)
    inp(be, rr, 3, b.danger_num / b.danger_den, "0.00x")
    inp(be, rr, 4, b.hp_per_ring); inp(be, rr, 5, b.ring_cap)
    inp(be, rr, 6, b.spot_rarity_per_ring / 100, PCT)
    has = any(b.id in a.biomes for a in ACTIONS) and any(rg.biome == b.id for rg in REG)
    put(be, rr, 7, "in play" if has else "terrain only, no regions or encounters yet", NOTE if not has else BLACK)
rr = 6 + len(BIOMES)
put(be, rr, 1, "Regions", TITLE)
header(be, rr + 1, ["Region", "Name", "Biome", "Pick weight", "Share of cells", "Tree canopy %", "Brush %",
                    "Look", "Sites that can appear (per-mille)"])
REG_FIRST = rr + 2
for i, rg in enumerate(REG):
    q = REG_FIRST + i
    put(be, q, 1, rg.id); put(be, q, 2, rg.name); put(be, q, 3, rg.biome)
    inp(be, q, 4, rg.weight)
    put(be, q, 5, f"=D{q}/SUM($D${REG_FIRST}:$D${REG_FIRST + len(REG) - 1})", fmt=PCT)
    inp(be, q, 6, rg.canopy); inp(be, q, 7, rg.brush); put(be, q, 8, rg.landmark)
    put(be, q, 9, ", ".join(f"{s.name} {s.weights[rg.id]}" for s in SITES.values() if rg.id in s.weights))
rr = REG_FIRST + len(REG) + 1
put(be, rr, 1, "Enemies", TITLE)
header(be, rr + 1, ["Enemy", "Name", "Fight spot", "Hit at ring 0", "HP at ring 0", "Biome", "Charges within (steps)",
                    "One step every (ms)", "Leash (tiles from home)"])
EN_ROW = {}
for i, e in enumerate(ENEMIES.values()):
    q = rr + 2 + i
    EN_ROW[e.id] = q
    spot = next(a for a in ACTIONS if a.enemy == e.id and a.placement in ("spot", "site"))
    put(be, q, 1, e.id); put(be, q, 2, e.name)
    put(be, q, 3, ", ".join(a.id + (f" ({SITES[a.site].name})" if a.site else "") for a in ACTIONS if a.enemy == e.id))
    inp(be, q, 4, e.hit); inp(be, q, 5, spot.hp); put(be, q, 6, spot.biomes[0]); inp(be, q, 7, e.aggro_radius)
    inp(be, q, 8, e.step_ms); put(be, q, 9, e.leash if e.leash is not None else "none")
rr = rr + 3 + len(ENEMIES)
put(be, rr, 1, "Danger by ring", TITLE)
put(be, rr, 3, "Health is 100. Hits shown at base Endurance (its speed divides them); the game rounds down.", NOTE)
heads = ["Ring"]
for e in ENEMIES.values():
    heads += [f"{e.name} hit", f"{e.name} HP"]
header(be, rr + 1, heads)
for k, ring in enumerate(range(0, 11)):
    q = rr + 2 + k
    put(be, q, 1, ring)
    for j, e in enumerate(ENEMIES.values()):
        er, br = EN_ROW[e.id], BIO_ROW[next(a for a in ACTIONS if a.enemy == e.id and a.placement in ("spot", "site")).biomes[0]]
        capped = f"MIN($A{q},$E${br})"
        put(be, q, 2 + 2 * j, f"=INT($D${er}*$C${br}^{capped})", fmt="0")
        put(be, q, 3 + 2 * j, f"=$E${er}+$D${br}*{capped}", fmt="0")
widths(be, [16, 18, 14, 12, 12, 12, 16, 10, 60])
be.freeze_panes = "A5"

# ---------------------------------------------------------------- Exhaustion
xw = wb.create_sheet("Exhaustion")
title(xw, "Local exhaustion", f"Each harvest of a wild spot lowers that kind's spawn weight in its region cell "
      f"({REGION_CELL}x{REGION_CELL} chunks) for the rest of the life, down to the floor. Resets every life.")
put(xw, 4, 1, "Floor (% kept)", BOLD); inp(xw, 4, 2, PRESSURE_FLOOR / 100, PCT)
HARV = list(range(0, 9))
header(xw, 6, ["Kind", "Step per harvest", "Wild spots of this kind"] + [f"After {n}" for n in HARV])
for i, eco in enumerate(ECOLOGY):
    r = 7 + i
    put(xw, r, 1, eco)
    inp(xw, r, 2, PRESSURE_STEP[eco] / 100, PCT)
    put(xw, r, 3, ", ".join(a.name for a in ACTIONS if a.ecology == eco))
    for j, n in enumerate(HARV):
        put(xw, r, 4 + j, f"=MAX($B$4,1-$B{r}*{n})", fmt="0%")
put(xw, 8 + len(ECOLOGY), 1, "Spawn weight left (x the encounter's normal weight) after that many harvests in one cell. "
    "Leads, sites and enemies never deplete.", NOTE)
widths(xw, [14, 16, 40] + [9] * len(HARV))

# ---------------------------------------------------------------- Site conditions
kw = wb.create_sheet("Site conditions")
title(kw, "Site conditions", "Each landmark has one condition per life, picked by weight among those that fit its structure.")
header(kw, 4, ["ID", "Name", "Weight", "Fits", "Site encounters", "Adds in the clearing", "Site work time",
               "Bonus drops", "Shown to the player"])
CR = 5
for i, c in enumerate(SITE_CONDITIONS.values()):
    r = CR + i
    for j, v in enumerate([c.id, c.name, c.weight, ", ".join(c.structures) if c.structures else "any site",
                           f"{c.spots_delta:+d}" if c.spots_delta else "as rolled",
                           ", ".join(BY_ID[a].name for a in c.adds) or "-", c.duration_percent / 100,
                           "yes" if c.drops else "no", c.text], 1):
        put(kw, r, j, v, fmt="0%" if j == 7 else None)
    inp(kw, r, 3, c.weight)
last = CR + len(SITE_CONDITIONS) - 1
header(kw, last + 2, ["Site", "Structure"] + [c.name for c in SITE_CONDITIONS.values()])
for i, site in enumerate(SITES.values()):
    r = last + 3 + i
    put(kw, r, 1, site.name); put(kw, r, 2, site.structure)
    fits = [CR + k for k, c in enumerate(SITE_CONDITIONS.values()) if c.structures is None or site.structure in c.structures]
    total = "+".join(f"$C${row}" for row in fits)
    for k, c in enumerate(SITE_CONDITIONS.values()):
        ok = c.structures is None or site.structure in c.structures
        put(kw, r, 3 + k, f"=$C${CR + k}/({total})" if ok else 0, fmt="0%")
pr = last + 4 + len(SITES)
put(kw, pr, 1, "Rare phenomena (small impossible things; never currency)", BOLD)
header(kw, pr + 1, ["ID", "Name", "Where", "Rarity / placement", "Effect"])
for i, aid in enumerate(("hanging_leaf", "backward_ripple", "double_shadow", "split_shadow_tree")):
    a = BY_ID[aid]
    where = ", ".join(a.regions) if a.regions else ("beside water" if a.near == "w" else "from a mossy rock" if aid == "double_shadow"
                                                    else "near the double shadow, a chunk away")
    effect = "; ".join(f"{o.kind} {o.id}" + (f" ({o.chance}%)" if o.chance < 100 else "") for o in a.outcomes)
    for j, v in enumerate([aid, a.name, where, f"{a.rarity} {a.placement}", effect], 1):
        put(kw, pr + 2 + i, j, v)
put(kw, pr + 7, 1, f"Shimmer: uncommon and rare spot odds x{SHIMMER_RARITY_PERCENT / 100:g} in that region cell "
    f"({REGION_CELL}x{REGION_CELL} chunks) for the rest of the life (tier caps still apply).", NOTE)
widths(kw, [18, 18, 10, 30, 14, 20, 12, 10, 44])
kw.freeze_panes = "A5"

# ---------------------------------------------------------------- Items
iw = wb.create_sheet("Items")
title(iw, "Items", "Treasure = no use during a life, carried home for ash.")
header(iw, 4, ["ID", "Name", "Kind", "Rarity", "Food", "Ash value", "Slot", "Comes from"])
for i, (iid, it) in enumerate(ITEMS.items()):
    r = 5 + i
    src = [a.id for a in ACTIONS if any(lo.item == iid for lo in a.loot) or a.effect == iid]
    src += [f"bonus:{t.id}" for t in tables if iid in flat(t.id) and any(p.item == iid for pool in t.pools.values() for p in pool)]
    for j, v in enumerate([iid, it.name, it.kind, it.rarity, it.food or "", it.ash_value, it.slot or "", ", ".join(src)], 1):
        put(iw, r, j, v, fill=TIER_FILL[it.rarity])
    inp(iw, r, 6, it.ash_value)
iw.freeze_panes = "B5"
widths(iw, [16, 16, 10, 10, 6, 9, 8, 50])

order = ["Read me", "Tiers", "Encounters", "Sites", "Site encounters", "Regions", "Biomes & enemies", "Spawn odds",
         "Fixed loot", "Drop tables", "Bonus drops", "Chains", "Crafts & buildings", "Carry load", "Exhaustion", "Site conditions", "Items"]
wb._sheets = [wb[n] for n in order] + [w for w in wb.worksheets if w.title not in order]
for s in wb.worksheets:
    s.sheet_view.showGridLines = False
wb.save(OUT)
print("saved", OUT)
