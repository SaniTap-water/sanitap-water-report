# DRAFT — note to mWater support (not sent)

Drafted 23 September 2026 for Adriaan Mol to review and send. Nothing in the report depends
on it: the region for these points is held in `data/register_corrections.json` permanently.

---

**Subject:** Madagascar admin boundaries appear to clip the Antongil Bay shore. Nine water points get no admin_region.

Hello,

Nine water points in our group (MadAvance, `group:aaaf0a14e4ce44eaa7a2bcfd1c74aa56`), all in
Maroantsetra district, Madagascar, have no `admin_region`. All their other fields are complete.
We think the Madagascar boundary data clips the shoreline of Antongil Bay.

A jsonql `ST_Intersects` query against `admin_regions.shape` returns no region, at any level
including the country, for any of the nine locations. Each point lies between 1 and 91 m outside
the nearest polygon. Their nearest neighbours in the register, 19 to 490 m away, fall inside all five levels and are
assigned normally.

| code | latitude | longitude | outside nearest polygon by | nearest fokontany polygon |
|---|---|---|---|---|
| 698771103 | -15.483088 | 49.665198 | 13 m | Antoraka (303143) |
| 698771251 | -15.5429355 | 49.6202416 | 1 m | Ambodipaka (308394) |
| 699596004 | -15.4863382 | 49.6626181 | 69 m | Antoraka (303143) |
| 698771244 | -15.5418162 | 49.6207956 | 9 m | Ambodipaka (308394) |
| 742897232 | -15.4132043 | 49.8612331 | 91 m | Navana (303144) |
| 698771110 | -15.484701 | 49.664297 | 71 m | Antoraka (303143) |
| 742897115 | -15.4130945 | 49.8631942 | 9 m | Navana (303144) |
| 699596114 | -15.5199504 | 49.6334724 | 12 m | Manambia (303141) |
| 742897074 | -15.4129472 | 49.8592585 | 37 m | Navana (303144) |

(Distances are approximate: Mercator distance × cos(latitude).)

We have no reason to think the coordinates are wrong, and we would rather not move points to fit
the boundary. Could the Madagascar boundaries be checked along this coast? The same clipping
would presumably affect any coastal site there. If the country and fokontany polygons are
extended to the shoreline, these nine should pick up their regions on their own.

We tried writing `admin_region` directly through the v3 entities API once. The PATCH was
accepted and the field discarded, which we take to be expected for a computed field.

Thank you,
Adriaan Mol, SaniTap
