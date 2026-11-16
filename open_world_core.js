/* Mars EVA Navigator — measured Martian DEM geometry, shared by browser and tests.
   Raster row zero is NORTH. X increases east and Z increases south, metres.
   NoData cells are never interpolated as observed terrain. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.MarsTerrainCore = api;
})(globalThis, function () {
  'use strict';
  const R = 3396190; // Mars spherical working radius, metres (not Earth WGS84).
  const RAD = Math.PI / 180;
  const finite = (v) => typeof v === 'number' && Number.isFinite(v);
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  function readDEM(data) {
    if (!data || data.elevation_units !== 'm' ||
        data.coordinate_order !== 'longitude, latitude') throw Error('Unidades o coordenadas DEM no válidas.');
    const w = data.width, h = data.height;
    if (!Number.isInteger(w) || !Number.isInteger(h) || w < 40 || h < 40 ||
        w > 2000 || h > 2000 || !Array.isArray(data.elevations) ||
        data.elevations.length !== w * h) throw Error('Dimensiones DEM incompatibles.');
    const bbox = data.bbox;
    if (!Array.isArray(bbox) || bbox.length !== 4 || !bbox.every(finite) ||
        !(76 < bbox[0] && bbox[0] < bbox[2] && bbox[2] < 79 &&
          17 < bbox[1] && bbox[1] < bbox[3] && bbox[3] < 20)) {
      throw Error('La cobertura del DEM no corresponde a Jezero.');
    }
    const dx = (bbox[2] - bbox[0]) * R * RAD *
      Math.cos((bbox[1] + bbox[3]) * 0.5 * RAD) / w;
    const dz = (bbox[3] - bbox[1]) * R * RAD / h;
    if (!(dx > 0 && dz > 0)) throw Error('Escala métrica inválida.');
    let min = Infinity, max = -Infinity, validCount = 0;
    const values = new Float64Array(w * h);
    const mask = new Uint8Array(w * h);
    for (let i = 0; i < values.length; i++) {
      const v = data.elevations[i];
      if (finite(v) && Math.abs(v) < 100000) {
        values[i] = v; mask[i] = 1; validCount++;
        min = Math.min(min, v); max = Math.max(max, v);
      } else if (v !== null) {
        throw Error('Valores DEM inválidos; NoData debe ser null.');
      }
    }
    if (validCount / values.length < 0.7) throw Error('Cobertura DEM insuficiente (<70%).');
    const ratio = validCount / values.length;
    if (finite(data.valid_fraction) && Math.abs(ratio - data.valid_fraction) > 0.0001)
      throw Error('Máscara DEM incoherente con valid_fraction.');
    const reference = values[mask.findIndex(v => v === 1)];
    // Prefix sum: prevents LOD triangles bridging gaps hidden at coarse grid sizes.
    const stride = w + 1, missing = new Uint32Array(stride * (h + 1));
    for (let r = 1; r <= h; r++) for (let c = 1; c <= w; c++) {
      missing[r * stride + c] = (mask[(r - 1) * w + c - 1] ? 0 : 1) +
        missing[(r - 1) * stride + c] + missing[r * stride + c - 1] -
        missing[(r - 1) * stride + c - 1];
    }
    return { w, h, dx, dz, bbox: bbox.slice(), values, mask, missing, stride,
      ref: reference, min, max, validFraction: ratio, raw: data };
  }
  function missingInBox(d, r0, c0, r1, c1) {
    // Inclusive source-pixel rectangle, so no coarse quad bridges an unmapped cell.
    const a = d.stride, m = d.missing;
    return m[(r1 + 1) * a + c1 + 1] - m[r0 * a + c1 + 1] -
      m[(r1 + 1) * a + c0] + m[r0 * a + c0];
  }
  function xAt(d, c) { return (c + 0.5 - d.w / 2) * d.dx; }
  function zAt(d, r) { return (r + 0.5 - d.h / 2) * d.dz; }
  function geoAt(d, x, z) {
    const c = x / d.dx + d.w / 2, r = z / d.dz + d.h / 2;
    return {
      lon: d.bbox[0] + (c / d.w) * (d.bbox[2] - d.bbox[0]),
      lat: d.bbox[3] - (r / d.h) * (d.bbox[3] - d.bbox[1])
    };
  }
  function pointAt(d, lon, lat) {
    return {
      x: ((lon - d.bbox[0]) / (d.bbox[2] - d.bbox[0]) - 0.5) * d.w * d.dx,
      z: ((d.bbox[3] - lat) / (d.bbox[3] - d.bbox[1]) - 0.5) * d.h * d.dz
    };
  }
  function sample(d, x, z) {
    const c = x / d.dx + d.w / 2 - 0.5, r = z / d.dz + d.h / 2 - 0.5;
    if (c < 0 || r < 0 || c > d.w - 1 || r > d.h - 1) return null;
    const c0 = Math.floor(c), r0 = Math.floor(r);
    const c1 = Math.min(d.w - 1, c0 + 1), r1 = Math.min(d.h - 1, r0 + 1);
    const a = r0 * d.w + c0, b = r0 * d.w + c1;
    const f = r1 * d.w + c0, g = r1 * d.w + c1;
    if (!d.mask[a] || !d.mask[b] || !d.mask[f] || !d.mask[g]) return null;
    const tx = c - c0, tz = r - r0;
    return (d.values[a] * (1 - tx) + d.values[b] * tx) * (1 - tz) +
      (d.values[f] * (1 - tx) + d.values[g] * tx) * tz;
  }
  function slope(d, x, z) {
    const w = sample(d, x - d.dx, z), e = sample(d, x + d.dx, z);
    const n = sample(d, x, z - d.dz), s = sample(d, x, z + d.dz);
    if ([w,e,n,s].some(v => v === null)) return null;
    return Math.atan(Math.hypot((e - w) / (2 * d.dx),
      (s - n) / (2 * d.dz))) / RAD;
  }
  function findStart(d) {
    const c0 = Math.floor(d.w / 2), r0 = Math.floor(d.h / 2);
    for (let rad = 0; rad < Math.max(d.w,d.h); rad++) {
      for (let r = Math.max(0,r0-rad); r < Math.min(d.h,r0+rad+1); r++) {
        for (let c = Math.max(0,c0-rad); c < Math.min(d.w,c0+rad+1); c++) {
          if (!d.mask[r*d.w+c]) continue;
          const x = xAt(d,c), z = zAt(d,r);
          if (sample(d,x,z) !== null) return {x,z,height:d.values[r*d.w+c]};
        }
      }
    }
    throw Error('No hay punto de inicio con elevación válida.');
  }
  function shade(d, elevation, slopeFactor = 0) {
    const t = clamp((elevation - d.min) / Math.max(1, d.max - d.min), 0, 1);
    const s = clamp(slopeFactor,0,1);
    return [
      clamp(0.43 + 0.30 * t - s * 0.08, 0, 1),
      clamp(0.25 + 0.24 * t - s * 0.05, 0, 1),
      clamp(0.19 + 0.20 * t - s * 0.03, 0, 1)
    ];
  }
  function chunk(d, row, col, span = 32, step = 1) {
    if (!Number.isInteger(step) || step < 1 || !Number.isInteger(span) || span < 2)
      throw Error('LOD inválido.');
    const lastR = Math.min(d.h - 1, row + span), lastC = Math.min(d.w - 1, col + span);
    const rs = [], cs = [];
    for (let r = row; r < lastR; r += step) rs.push(r);
    for (let c = col; c < lastC; c += step) cs.push(c);
    if (rs.at(-1) !== lastR) rs.push(lastR);
    if (cs.at(-1) !== lastC) cs.push(lastC);
    const vertices = [], uvs = [], colors = [], indices = [];
    for (const r of rs) for (const c of cs) {
      const height = d.values[r*d.w+c];
      vertices.push(xAt(d,c), d.mask[r*d.w+c] ? height - d.ref : 0, zAt(d,r));
      uvs.push((c+0.5)/d.w, 1-(r+0.5)/d.h);
      colors.push(...shade(d,height));
    }
    const nC = cs.length;
    for (let ri=0;ri<rs.length-1;ri++) for (let ci=0;ci<cs.length-1;ci++) {
      if (missingInBox(d,rs[ri],cs[ci],rs[ri+1],cs[ci+1])) continue;
      const a=ri*nC+ci, b=a+1, c=a+nC, e=c+1;
      indices.push(a,c,b,b,c,e);
    }
    return {vertices:new Float32Array(vertices),uvs:new Float32Array(uvs),
      colors:new Float32Array(colors),indices:new Uint32Array(indices),
      centerX:xAt(d,(col+lastC)/2),centerZ:zAt(d,(row+lastR)/2)};
  }
  return {R, readDEM, sample, slope, xAt, zAt, geoAt, pointAt,
    findStart, missingInBox, chunk, shade};
});