// Test why mWater gives the nine Maroantsetra points no admin_region.
//
// mWater assigns admin_region itself from the GPS location (the water_point
// schema: "assigned automatically by mWater based on the GPS location"). For
// each point this asks mWater's own admin_regions table, through jsonql,
// which boundary polygons contain the location and how far the point is from
// the nearest one - and, as a control, the same for its nearest coded
// neighbour. Read-only; no entity is written.
//
//   node tools/mwater/admin_polygon_test.mjs     # writes data/admin_polygon_test.json

import fs from "node:fs";
import { apiGet } from "./api.mjs";
const NINE = ["698771103","698771251","699596004","698771244","742897232","698771110","742897115","699596114","742897074"];
const all = [];
for (let skip = 0; ; skip += 500) {
  const r = await apiGet("entities/water_point", {filter: JSON.stringify({ _managed_by: "group:aaaf0a14e4ce44eaa7a2bcfd1c74aa56" }), limit: 500, skip});
  if (!r.length) break; all.push(...r); if (r.length < 500) break;
}
const hav = (a, b) => { const R=6371000,r=Math.PI/180; const dLat=(b[1]-a[1])*r,dLon=(b[0]-a[0])*r; const s=Math.sin(dLat/2)**2+Math.cos(a[1]*r)*Math.cos(b[1]*r)*Math.sin(dLon/2)**2; return 2*R*Math.asin(Math.sqrt(s)); };
const F = (c)=>({type:"field",tableAlias:"m",column:c});
const L = (v)=>({type:"literal",value:v});
const P = (lon,lat)=>({type:"op",op:"ST_Transform",exprs:[{type:"op",op:"ST_SetSRID",exprs:[{type:"op",op:"ST_MakePoint",exprs:[L(lon),L(lat)]},L(4326)]},L(3857)]});
const op=(o,...e)=>({type:"op",op:o,exprs:e});
async function inside(lon,lat){
  const q={type:"query",selects:[{type:"select",expr:F("_id"),alias:"id"},{type:"select",expr:F("level"),alias:"level"},{type:"select",expr:F("name"),alias:"name"}],
    from:{type:"table",table:"admin_regions",alias:"m"}, where: op("ST_Intersects",F("shape"),P(lon,lat)), orderBy:[{ordinal:2}]};
  return apiGet("jsonql",{jsonql:JSON.stringify(q)});
}
async function nearest(lon,lat,level){
  const d = op("ST_Distance",F("shape"),P(lon,lat));
  const q={type:"query",selects:[{type:"select",expr:F("_id"),alias:"id"},{type:"select",expr:F("name"),alias:"name"},{type:"select",expr:d,alias:"d"}],
    from:{type:"table",table:"admin_regions",alias:"m"},
    where: op("and", op("=",F("level0"),L(133)), op("=",F("level"),L(level)), op("ST_DWithin",F("shape"),P(lon,lat),L(50000))),
    orderBy:[{ordinal:3,direction:"asc"}], limit:1};
  const r = await apiGet("jsonql",{jsonql:JSON.stringify(q)});
  return r[0] ? {...r[0], m: Math.round(r[0].d*Math.cos(lat*Math.PI/180))} : null;
}
const out = [];
for (const code of NINE) {
  const e = all.find(x=>x.code===code);
  const [lon,lat] = e.location.coordinates;
  const ins = await inside(lon,lat);
  const n0 = await nearest(lon,lat,0), n4 = await nearest(lon,lat,4);
  // control: nearest coded managed point
  const ctl = all.filter(o=>o.admin_region!=null && o.location?.coordinates).map(o=>({o,d:hav(e.location.coordinates,o.location.coordinates)})).sort((a,b)=>a.d-b.d)[0];
  const cins = await inside(...ctl.o.location.coordinates.slice(0,2));
  const row = {code, lat, lon, admin_region: e.admin_region ?? null, admin_div: [e.admin_div1,e.admin_div2,e.admin_div3,e.admin_div4].join("/"),
    polygons_containing: ins.map(r=>`${r.level}:${r.name}`), nearest_country_m: n0?.m, nearest_fokontany: n4 && `${n4.id} ${n4.name}`, nearest_fokontany_m: n4?.m,
    control: {code: ctl.o.code, dist_m: Math.round(ctl.d), admin_region: ctl.o.admin_region, polygons_containing: cins.map(r=>`${r.level}:${r.name}`)}};
  out.push(row); console.log(JSON.stringify(row));
}
fs.writeFileSync("/home/bushp/sanitap-water-report/data/admin_polygon_test.json", JSON.stringify({tested_on: new Date().toISOString().slice(0,10), method: "jsonql ST_Intersects / ST_Distance on admin_regions.shape (EPSG:3857); metres = Mercator distance x cos(latitude)", points: out}, null, 1) + "\n");
