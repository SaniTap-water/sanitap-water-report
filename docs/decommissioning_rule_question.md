# The decommissioning rule: decision record

> **Denominator corrected 2026-09-22.** The active carbon point count used here was **727**, which is not derivable from any data in this repository. It is now **731** — the actively managed register less Marolinta, computed every build. See the decision log entry of 22 September 2026. The figures below are left as written on the date stated; the report itself carries the corrected denominator.


## Decision, 21 September 2026

**SaniTap will not decommission or retire water points for inactivity.**

A pump that stays broken is a repair problem, not a register problem. It remains in the
portfolio and is reported at its honest days operational.

The reasoning is conservatism. Removing under-performing points takes them out of the
denominator and flatters the fleet average: the worst points would leave the register and the
reported availability of what remained would rise, without a single pump working better. That is
the less conservative treatment and the one a verifier would question. Keeping a broken pump in
the portfolio at its real `DO` is the harder number to report and the easier one to defend.

It is also what the methodology already assumes. Neither version has any provision for a retired
supply, because none is needed — `DO_p,y` is days operational, and a pump that stops working
simply contributes fewer of them.

**What follows from the decision**

* The 95% pause rule in `SOP-Suppression_Points d'Eau` is not applied, and the SOP should be
  amended to say so. The English SOP, which never carried a pause section, is already correct.
* The permanent-deletion criteria are unaffected: duplicate records, confirmed persistent
  contamination, irreparable or abandoned infrastructure, serious persistent health or safety
  risk, points taken over by another funder, no access. None of those is an availability
  judgement and all of them stand.
* **No writable status property is needed in the register.** The only thing it was wanted for
  was a "paused" state, and there is no longer a paused state. Excluding a record that is not a
  water point at all is a separate and much smaller job, and the `ZZ TEST` name-prefix
  convention in `tools/exclude_retired.py` already does it for the two such records that exist.
* **Repair speed becomes the only lever on days operational.** That is why time to repair is now
  a headline metric on the report rather than an operational detail.

The analysis that led here is kept below, unchanged, as the reasoning.

---

## 1. What the SOPs say the field does

Both decommissioning SOPs — `SOP-Suppression_Points d'Eau` (French) and `SOP for
Decommissioning Water Points` (English) — build their availability rule on a *days of
inactivity* count, and name an mWater field that holds it:

> *"App mobile mWater (formulaire de suivi personnalisé avec champ « jours d'inactivité »)
> pour ceux qui en ont l'accès."*

> *"mWater mobile app (customized tracking form with 'days of inactivity' field) for those
> with access."*

**That field exists on none of the twelve live forms.** It is not mis-named or mis-remembered:
no question on any form matches *inactivit* or *days of inactivity*.

But the underlying observation is not missing. The SOPs describe where it comes from:

> *"Le gardien de l'eau note chaque jour d'inactivité : il coche une case ou inscrit la date à
> chaque fois que la pompe n'a pas fonctionné (quelle qu'en soit la raison)."*

> *"Il reporte le nombre de jours d'inactivité observés sur la période (ex : les 90 derniers
> jours ou depuis la dernière visite). Ces informations sont saisies dans la base de données
> (mWater ou Excel) via le formulaire prévu à cet effet (formulaire mWater sur les réparations
> après panne ou les maintenances préventives)."*

**That is the gardien calendar.** The SOPs' availability formula is the calendar SOP's formula,
word for word in substance:

> *"Taux de disponibilité (%) = 100 × (Nombre de jours sur la période – Jours d'inactivité
> notés) / Nombre de jours sur la période"*

So the gap is narrower and more specific than "a missing field". **The observation is collected
— as a photograph. It is the transcription into a number that was never built.** Today the
count exists only as ticks on paper that nobody has totalled, which is why the extraction work
in this report exists at all.

## 2. The threshold, and the number it happens to equal

The French SOP sets a pause rule. **The English SOP has no pause section at all** — it covers
only permanent deletion. That divergence between the two is itself unresolved.

> *"Un point d'eau est placé en « pause » s'il présente un taux de disponibilité fonctionnelle
> inférieur à 95 % sur une période de référence (ex : 12 mois), sans autre motif direct de
> suppression. (SDWS27)"*

> *"La « mise en pause » signifie que le point d'eau est temporairement non comptabilisé comme
> actif pour l'accès à l'eau ou les crédits carbone."*

> *"Le point d'eau peut être réactivé une fois la disponibilité restaurée (> 95 %)."*

**95% of 365 days is 346.75 days.** The registered basis caps `DO_p,y` at **347**. The pause
threshold and the carbon assumption are, to within a rounding, the same number: a point that
falls below the availability the project assumes is, by this SOP, to stop being counted. Whether
that alignment was intended is not recorded anywhere, and it matters, because it means the rule
is not a housekeeping rule — it is a rule about the carbon boundary, written in an operations
SOP and tagged `(SDWS27)`.

Permanent deletion is separate and is not availability-based. The French SOP lists: duplication
in the database; confirmed persistent contamination (SDWS 3); durably insufficient productivity
(flow below the minimum threshold even at low water); infrastructure irreparable or abandoned;
serious and persistent health or safety risk; a point taken over by another funder; other
justified reasons such as impossible access or permanent vandalism. The English list adds
toilets built within 30 m with confirmed contamination, and puts a six-month qualifier on the
productivity criterion — where it also carries an unresolved note in the document itself:
*"Trouver une methode de calcul basée sur ces besoins estimés de la GS (revised version)"*. The
flow threshold the criterion depends on is therefore not settled either.

## 3. How points are actually retired today

**By the record's name, and twice.**

The register holds **908** water-point records. Exactly **two** are retired, and they are
retired by a `ZZ TEST` prefix on the name:

| code | name | why |
|---|---|---|
| `924119262` | `ZZ TEST - NOT A WATER POINT AEPG` | the photograph is a potted plant |
| `927104201` | `ZZ TEST - NOT A WATER POINT AEP` | the photograph is a village street |

Both are data-quality exclusions — records that were never water points. **No point has ever
been retired or paused for inactivity, availability, contamination or productivity.**

The name prefix is not a design choice, it is the only door left open. All 236 properties on the
`water_point` entity type carry a `roles` list, and every status-like property is reserved to
another organisation's group; writing one returns HTTP 403. The only properties this account can
write are `name`, `desc` and `type`, and `type` is load-bearing elsewhere. So:

**There is no way to express "paused" in the register at all.** The SOP defines a temporary
status that the database cannot hold. A pause would today have to be either a permanent-looking
name change or an off-system list.

## 4. How many points a threshold would touch

From the calendar extraction, per pump-period, on observed cells only. **These are machine
readings and the accuracy assessment against human transcription is still outstanding**, so they
size the decision; they do not make it. The extraction's own false-positive floor, measured on
impossible cells, is **1.84%**, and a threshold applied to raw readings will therefore flag
points that are simply noisy. Both are shown.

| observed window | points | below 95% (raw) | below 95% (floor-adjusted) | below 90% (adjusted) |
|---|---|---|---|---|
| ≥ 90 days | 255 | 90 | **48** | 3 |
| ≥ 180 days | 225 | 61 | **29** | 2 |

Floor-adjusted, **19%** of points with a ≥90-day window sit below 95% availability, and **13%**
of those with a ≥180-day window. Scaled across the **727** active carbon points — an
extrapolation from the points that happen to have readable calendars, which is not a random
sample — that is roughly **95 to 140 points**.

At **27.9 tCO₂e** per community water supply per year, pausing that many points forgoes on the
order of **2,600 to 3,900 tCO₂e a year**, about **USD 52,000 to 78,000** at USD 20/t. The range
is wide because the input is uncalibrated, and it will narrow when the transcription round
reports.

The counter-figure: the whole 2026 evidence gap is **17,681 tCO₂e**. Retirement is a smaller
number than the evidence problem, and the two interact — a point with no calendar photograph has
no measured availability, so under a strict reading of the rule it cannot be shown to be above
95% either.

## 5. What the methodology says

**Nothing.** The words *decommission*, *abandon* and *dismantle* appear **zero times** in both
the registered v1.0 and in v2.0. There is no provision for a supply retired part-way through a
monitoring period and no instruction on how to treat its emission reductions.

What the methodology does instead is make the question largely disappear into the parameter:

> *"𝐷𝑂𝑝,𝑦 = Days the project technology is operational for end-users in premises p in year y"*

A point that stops working simply has fewer operational days that year. The arithmetic already
handles a partial year, and `Q_pop,y = Σ_p HH × HN × QPW × DO_p,y` sums over premises, so a
point that ceases mid-year contributes what it actually delivered. **On the face of the
methodology, a retired point does not need to be removed from the register — it needs an honest
`DO`.** The only place either version subtracts days rather than points is the back-up
technology rule in v1.0: *"the number of ineligible days shall be subtracted from DOp,y"*.

Two provisions cut the other way and should be in front of Jan:

* **v2.0 §3.2.7.1** — *"Where the technical life of the technology (SDWS 7) is shorter than the
  crediting period, the developer shall provide replacement or retrofit measures with a
  performance guarantee; otherwise emission-reduction claims are limited to the technical
  life."* A point left in the register but not maintained is a claim beyond technical life.
* **v2.0 embodied-emissions leakage** — the deduction runs *"for exactly five full years from
  their respective dates of commissioning, regardless of whether individual units break or drop
  out of the active operational fleet."* **Retiring a point removes its emission reductions but
  does not remove its embodied-emissions leakage.** Retirement is therefore not cost-neutral for
  units commissioned inside the crediting period; the default factor is per Table 9 §9.2 and the
  per-unit figure has not been applied here.

## 6. The options as they stood

**The choice was between three positions differing by roughly 3,000 tCO₂e a year and by how
much a verifier could challenge. Option B was taken, for the reason at the top of this file: it
is the conservative one.**
*Option A — apply the French SOP as written*: pause every point below 95% availability over
twelve months, which on present uncalibrated readings is something like 95 to 140 points and
forgoes on the order of 2,600 to 3,900 tCO₂e a year, needs a status the register cannot
currently hold, and requires the availability figure to be defensible per point — which today it
is not, because the extraction is unvalidated and most points have less than a full year of
photographic evidence. *Option B — drop the availability-based pause and retire only on the
permanent-deletion criteria* (duplicate, confirmed contamination, irreparable or abandoned,
taken over, no access): costs nothing in tonnes, matches what is actually being done, and is
what the English SOP already says — but it leaves the project publishing a figure for points its
own French SOP says should not be counted, which is exactly the kind of internal contradiction a
VVB reads as a control failure. *Option C — keep a threshold but set it where the evidence can
carry it*, for example 90% floor-adjusted, which touches 2 to 3 points and costs under
100 tCO₂e a year, and defer the 95% rule until the transcription round has calibrated the
extraction. **What none of the three can be is the present position**, where one SOP sets a
carbon-relevant threshold, the other omits it, the database cannot express the status either
defines, and the field both rely on does not exist.

Whichever is chosen, three things follow and are not optional: the two SOPs have to say the same
thing; the rule has to be expressible in the register, which today means either getting write
access to a status property from mWater or accepting the name-prefix convention as the
mechanism; and a point that is retired mid-period still needs a defensible `DO` for the days it
did operate, because the methodology asks for days and not for membership.

## 7. What this document does not settle

The decision above settles whether to retire for inactivity. It does not settle these:

* Whether the 95%/347-day alignment was deliberate. Nothing on file says.
* The minimum flow threshold the productivity criterion depends on — the English SOP carries an
  open note saying the calculation method still has to be found.
* The per-unit embodied-emissions factor, and therefore the tonnage cost of retiring a
  commissioned unit under v2.0.
* Whether any point has been retired off-system, by WhatsApp or Asana as the SOPs permit, without
  reaching the register. The register can only show what reached it.
