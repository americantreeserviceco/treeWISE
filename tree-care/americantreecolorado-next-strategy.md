# American Tree Colorado: Next Strategy Playbook (v4)

**Built from:** the Duck.ai "Tree Care Intelligence" playbook, checked against the code in `tree-care/` and the live data sources.
**Date:** 2026-11-20
**Median data:** Census ACS 5-year 2019–2023, public bulk files (no API key).

---

## 0. Decisions taken

| Decision | Source | What it changes |
|---|---|---|
| **Base is Golden** | Owner | Distance rings measured from Golden (39.7555, -105.2211) |
| **Three services:** pruning, Full-Zone Root Nourishment (fertilization), winter watering | Owner | EAB injection, removal, stump grinding, storm and emergency work are out of this plan |
| **No customer or estimate system** | Owner | Conversion and route metrics start from a booking log (§4), not a CRM |
| **Start with local median** | Owner | ZIP targeting starts from median home value (primary) and median household income (secondary) |
| **Landscape and lawn firms are not competitors** | Owner | Excluded from competitor counts and the coverage review. Tree businesses only (e.g., "Tree & Landscape" still counts because it does tree work) |

**Readings I took (correct me if wrong):**
- The fertilization program is named "Full-Zone Root Nourishment" (formerly "tri-level" and "3-Tier Deep Root Nutrition"). It is the three-visit program.
- EAB preventative injection is **parked**.
- "Local median" is each ZIP's owner-occupied median home value and household income. Home value is the primary sort.

---

## 0b. Status as of v5 (tool changes made since v4)

| Item | Status |
|---|---|
| Median income and home value in the tool | Done. `zip_profile`: 527 Colorado ZIPs, 467 with income, 471 with home value |
| Distance from Golden in the dashboard | Done. Sidebar radius slider (5–50 mi). Ash trees, competitors and ZIPs all filter |
| Booking log in the dashboard | Done. Reads `booking-log.csv`; shows bookings and jobs by ZIP and service |
| Winter data beyond air temperature | Partly done. 30-day precipitation from the nearest NOAA station (Golden CoCoRaHS gauge, Denver Intl as backup) is in the rule. Soil temperature and frost are still not checked |
| Competitor coverage check | Done. `competitor_coverage.py` review list: 282 of 2,498 broad matches are caught now (the phrase list gained "tree & landscape"). About 638 tree-type names are still uncaught, and about 1,228 are landscape or lawn firms; the review CSV needs a manual pass |
| Other cities' tree data | Boulder publishes a public tree inventory on ArcGIS (layer "Trees in the City of Boulder Inventory"). Golden: no open inventory found (the city's forestry office is at 303-384-8141). Lakewood and Arvada: none found |

**Current winter result:** 30-day precipitation is 1.14 in, so under the 1.00 in rule every forecast period holds right now. The rule itself is an assumption, and it has a problem for winter watering: watering is usually needed when the soil is dry, but this rule treats dry as open for fertilization. The crew lead needs to set separate rules for the two services.

## 1. What changed in v4

These corrections come from fixing the scripts and re-checking the data. v3 had three of them wrong.

| Item | v3 said | v4 (checked) |
|---|---|---|
| Ash-tree count | "1,000 is a ceiling" (capped pull) | **33,479 unique ash trees** in the full Denver inventory |
| Ash-tree addresses | "House numbers only, no street" | Wrong. Every row has `street` (e.g., "E 9TH AVE") and `neighbor` (e.g., "Central Park"). Still public street trees, so no direct mail |
| Ash-tree dates | "2014–2016" | Inventory dates run **2014 to 2026**. Check `inventory_date` before using a tree as current |
| Ash-tree coverage | Implied all six service cities | **Denver city only.** Arvada, Lakewood, Highlands Ranch, Golden and Boulder are not in this dataset. A zero there means "not covered", not "no ash trees" |
| Competitor counts | 168 (broad name match) | **474** in target cities, using stricter name phrases. Counts are not comparable to v3 |
| Competitor location | City only; geocoding needed | Address and **ZIP** now stored, so ZIP-level counts need no geocoding |
| Foothill projects | Five records | **Removed.** Those were hardcoded fallback records. The ArcGIS source returned zero features on the last run |
| Winter forecast | BOU 78,87 (Boulder) | **BOU 55,63**, verified as the Golden grid |

---

## 2. Current tool status

| Source | Status | Rows |
|---|---|---|
| Denver ash-tree inventory | Loads in full, deduplicated | 33,479 |
| Colorado SOS tree businesses, target cities | Loads, deduplicated, with ZIP | 474 |
| Jefferson County projects (ArcGIS) | Source returns 0 features; old data removed | 0 |
| NWS winter forecast | Script ready; **needs `TREE_CARE_CONTACT` set** to a real contact | 0 |

**Not built yet:** the winter forecast has not been run, because the contact address is not set. Until it runs, the winter watering and fertilization windows have no data behind them.

---

## 3. Re-ranked strategy (Golden base, three services)

### Priority 1: Full-Zone Root Nourishment, median-first targeting
- **Why:** Core service. Median home value sets the order, so spend goes first to the highest-value ZIPs inside 15 miles of Golden.
- **Steps:**
  1. Start with the top five ZIPs in §4.
  2. Run ads and door-hangers there. Log every lead and booking (§5).
  3. After one cycle, compare cost per booking by ZIP. Drop the bottom ZIPs and add the next ones.
- **Metric:** Bookings per ZIP per month; cost per booking per ZIP.

### Priority 2: Winter watering
- **Why:** Same households as fertilization, cheap to add.
- **Steps:**
  1. Set `TREE_CARE_CONTACT` and run `winter_weather_fert.py` daily from November to February. It writes one row per forecast period.
  2. Have the crew lead sign off on the rule: forecast air temperature above 40°F and no snow in the forecast text. Soil, frost and 30-day rainfall are **not checked**.
  3. Offer watering to booked fertilization clients and the top ZIPs.
- **Metric:** Winter watering attach rate on fertilization bookings.

### Priority 3: Pruning
- **Why:** Largest ticket, least data. The Denver ash inventory can show mature tree density in Denver ZIPs, but it has no species beyond ash and no data outside Denver.
- **Steps:** Use median home value as the spend proxy. Add a "pruning requested" field to the booking log to measure demand.

### Priority 4: Golden-radius sales days
- **Why:** The crew works from Golden. §4 gives distance rings now.
- **Steps:** Schedule zone days inside 15 miles first. Track jobs per crew-hour in the booking log.

### Priority 5: Competitor gap (ZIP level, now possible)
- **Why:** The SOS data has ZIP codes, so gaps can be counted by ZIP without geocoding.
- **Current counts (unique businesses):** Denver 223, Boulder 44, Arvada 34, Lakewood 30, Golden 18, Highlands Ranch 11.
- **Steps:** Count competitors per ZIP in the target area. Compare against median and, for Denver ZIPs, against ash density.

### Parked
- **EAB preventative injection.** Not in the three services. The Denver ash data is still useful as a planning layer if the owner adds injection.
- **Municipal bids.** No municipal inventory or RFP feed. Monthly manual check only.

---

## 4. ZIP table: distance, median, and tree data

Distance is from Golden to the ZIP centroid (Census 2023 gazetteer). Ash counts assign each Denver tree to its nearest ZIP centroid, so they are approximate. **"Not covered"** means the ZIP is outside the Denver city inventory.

Median home value and median household income are ACS 2019–2023 5-year estimates. Income for 80302 is pulled down by students.

### Ranking: inside 15 miles of Golden, sorted by median home value

| Rank | ZIP | Miles | Area (verify) | Median home value | Median HH income | Denver ash trees (approx.) |
|---|---|---|---|---|---|---|
| 1 | 80206 | 14.4 | Denver (Cherry Creek) | $892,200 | $102,248 | 2,353 |
| 2 | 80210 | 14.8 | Denver (Washington Park area) | $870,500 | $120,156 | 1,934 |
| 3 | 80403 | 7.2 | Golden | $797,100 | $145,315 | Not covered |
| 4 | 80401 | 2.6 | Golden | $748,800 | $112,444 | Not covered |
| 5 | 80218 | 13.4 | Denver (Capitol Hill / Cheesman) | $653,900 | $82,925 | 1,092 |
| 6 | 80465 | 10.1 | Golden / Lakewood edge | $628,800 | $130,455 | Not covered |
| 7 | 80205 | 13.6 | Denver (Park Hill / Five Points) | $627,600 | $98,770 | 2,167 |
| 8 | 80005 | 8.2 | Arvada | $620,100 | $136,360 | Not covered |
| 9 | 80215 | 5.6 | Lakewood | $615,500 | $85,017 | Not covered |
| 10 | 80228 | 4.9 | Lakewood | $607,300 | $110,013 | Not covered |
| 11 | 80004 | 6.6 | Arvada | $590,600 | $99,576 | Not covered |
| 12 | 80226 | 7.5 | Lakewood | $547,000 | $78,466 | 1 |
| 13 | 80002 | 6.5 | Arvada | $538,900 | $92,827 | Not covered |
| 14 | 80227 | 8.9 | Lakewood | $535,000 | $88,796 | 35 |
| 15 | 80214 | 8.1 | Lakewood / Denver | $519,900 | $74,259 | 147 |
| 16 | 80223 | 12.3 | Denver (SW) | $497,900 | $80,461 | 708 |
| 17 | 80219 | 10.7 | Denver (W) | $426,200 | $67,325 | 730 |

**Just outside 15 miles:** 80303 Boulder $941,600 / $77,344 (15.1 mi); 80305 Boulder $985,700 / $120,933 (15.4 mi); 80302 Boulder $1,123,800 / $60,649 (19.8 mi); 80126 Highlands Ranch $713,500 / $166,501 (20.1 mi); 80129 Highlands Ranch $643,400 / $136,915 (18.2 mi); 80130 Highlands Ranch $652,700 / $155,117 (22.3 mi); 80301 Boulder $761,500 / $92,974 (20.1 mi).

### What the table says
- **The top two by median are Denver ZIPs with the most ash trees.** The inventory covers them, so the tree data supports them.
- **Golden ZIPs (80403 at rank 3, 80401 at rank 4) are closest to base but have no tree coverage.** Use the median and competitor counts to judge them, not the ash data.
- **Arvada and Lakewood ZIPs are not covered by the ash inventory.** They rank on median only.

---

## 5. Booking log (replaces the missing CRM)

`booking-log.csv` in this folder. One row per lead or booking:

| Column | Example |
|---|---|
| date | 2026-11-24 |
| zip | 80401 |
| source | ad / door-hanger / referral / phone / web form |
| service | pruning / full-zone root nourishment / winter watering |
| status | quoted / booked / completed / lost |
| job_value | (blank until invoiced) |
| notes | |

---

## 6. 90-day plan

| Window | Tasks | Owner (role) |
|---|---|---|
| **Weeks 1–2** | Set `TREE_CARE_CONTACT`. Run the winter forecast. Confirm the top five ZIPs. | Owner + developer |
| **Weeks 3–4** | Crew lead signs off on the winter rule and the fertilization claims. Start the booking log. | Crew lead + owner |
| **Weeks 5–6** | Launch Full-Zone Root Nourishment ads on the top five ZIPs (budget and approval needed first). | Owner |
| **Weeks 7–8** | Review first-cycle bookings by ZIP. Adjust the ZIP list. | Owner |
| **Weeks 9–12** | Launch winter watering offer to booked clients and top ZIPs. Test the 25-mile ring. | Owner |

---

## 7. Open questions for the owner

1. Confirm the program is three visits a year.
2. Is EAB injection parked for good?
3. Which contact address should go in `TREE_CARE_CONTACT`? It is needed before the winter forecast can run.
4. Is home value the right primary sort, or should income lead?

---

## 8. Monthly review

- **Data health:** `db_check.py` shows no duplicates; the pipeline exits 0; winter rows are added each run.
- **Bookings by ZIP and service:** from the booking log.
- **Winter watering attach rate.**
- **Median-ranked ZIP performance:** do the top-median ZIPs book at a better cost per booking?
- **Drop any ZIP or ad that books nothing in two cycles.**
