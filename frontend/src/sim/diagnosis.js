// Daily analysis: dry-up forecast plus a ranked list of findings.
// Each finding carries a message key and values so alerts can be written in en / mr / hi.
import { MONSOON_ONSET_DAY } from './constants.js';
import { normalRainForDay } from './rain.js';
import { clamp, fmtDay, fmtHM, median, regress } from './util.js';

export const SEVERITY_RANK = { ok: 0, watch: 1, act: 2, fault: 2.5, crit: 3 };
export const SEVERITY_LABEL = { ok: 'Healthy', watch: 'Watch', act: 'Act now', crit: 'Emergency', fault: 'Sensor fault' };

function forecast(s, swlNow, D, sensorFault) {
  const sc = s.sc;
  const day = s.lastDay;
  const limit = sc.intake - 2; // keep 2 m of water above the intake
  const fc = { swl: swlNow, D, limit };
  const rg = regress(s.daily.slice(-21).map((r) => [r.day, r.swl]));
  fc.rate = rg ? rg.m : NaN;

  if (sensorFault) fc.state = 'paused';
  else if (day >= MONSOON_ONSET_DAY) fc.state = 'monsoon';
  else if (!rg) fc.state = 'learning';
  else {
    const remaining = limit - D - swlNow;
    fc.remaining = remaining;
    const { m, se } = rg;
    if (remaining <= 0) {
      fc.state = 'dry';
      fc.p10 = fc.p50 = fc.p90 = day;
    } else if (m < 0.03) {
      fc.state = 'stable';
      fc.margin = remaining;
    } else {
      fc.p50 = day + remaining / m;
      fc.p10 = day + Math.max(0, remaining - 0.15 * D) / (m + 1.28 * se + 0.005);
      fc.p90 = day + (remaining + 0.15 * D) / Math.max(m - 1.28 * se, 0.02);
      fc.marginOnset = remaining - m * (MONSOON_ONSET_DAY - day);
      if (fc.p50 < MONSOON_ONSET_DAY) {
        fc.state = 'fail';
        const need = remaining / (MONSOON_ONSET_DAY - day);
        const pumpPart = Math.max(m - 0.03, 0.01);
        fc.cut = clamp(Math.ceil((1 - (need - 0.03) / pumpPart) * 20) * 5, 5, 90);
      } else fc.state = 'ok';
    }
  }
  return fc;
}

export function evaluate(s) {
  const sc = s.sc;
  const day = s.lastDay;
  const F = [];
  const cyc = s.cycles;
  const recentAll = cyc.filter((c) => c.day > day - 3 && !c.dry);
  const recent = cyc.filter((c) => c.day > day - 4 && !c.dry && c.sEnd > 0.3);
  const older = cyc.filter((c) => c.day <= day - 10 && c.day > day - 20 && !c.dry && c.sEnd > 0.3);
  const sensorFault = recentAll.length >= 2 && recentAll.slice(-2).every((c) => Math.abs(c.sEnd) < 0.08 && c.run > 0.4);
  const swlNow = s.daily.length ? s.daily[s.daily.length - 1].swl : s.swl;
  const D = Math.max(0.5, median(cyc.slice(-4).map((c) => c.sEnd).filter(Number.isFinite)) || 0) + 0.4;

  const fc = forecast(s, swlNow, D, sensorFault);
  s.forecast = fc;

  if (s.emergency && s.t - s.emergency.t < 36) {
    F.push({
      sev: 'crit',
      title: s.emergency.kind === 'dry' ? 'Pump cut off: water at intake' : 'Pump running dry',
      detail: 'Water reached ' + sc.intake + ' m at ' + fmtHM(s.emergency.t) + ' on ' + fmtDay(s.emergency.t / 24) + '.',
      msg: s.emergency.kind,
      v: { time: fmtHM(s.emergency.t) },
    });
  }

  if (sensorFault) {
    F.push({
      sev: 'fault',
      title: 'Depth reading not responding',
      detail: 'The last runs moved the reading less than 8 cm. Likely a false echo from a pipe joint near ' + recentAll[recentAll.length - 1].pre.toFixed(0) + ' m.',
      msg: 'sensor',
      v: {},
    });
  } else {
    const tR = median(recent.map((c) => c.T).filter(Number.isFinite)) / median(older.map((c) => c.T).filter(Number.isFinite));
    const scR = median(recent.map((c) => c.SC)) / median(older.map((c) => c.SC));
    const sR = median(recent.map((c) => c.sEnd)) / median(older.map((c) => c.sEnd));
    const iR = median(recent.map((c) => c.I)) / median(older.map((c) => c.I));
    const bigDD = median(recent.map((c) => c.sEnd)) > 2.2; // ratios are only trustworthy on measurable drawdown
    const swlOld = (s.daily.find((r) => r.day === day - 10) || { swl: swlNow }).swl;
    const crossed = sc.fr.some((f) => f.d >= swlOld - 2 && f.d <= swlNow + 2);

    if (bigDD && Number.isFinite(tR) && tR < 0.65 && crossed && scR >= tR * 0.8) {
      const fr = sc.fr.filter((f) => f.d <= swlNow + 1).sort((a, b) => b.d - a.d)[0];
      const dep = fr ? fr.d : Math.round(swlNow);
      F.push({
        sev: 'act', title: 'Fracture dewatered at ' + dep + ' m',
        detail: 'Transmissivity fell ' + Math.round((1 - tR) * 100) + '% in a week as the water table dropped past a water-bearing fracture.',
        msg: 'fracture', v: { depth: dep },
      });
    }

    const base = cyc.length ? cyc.filter((c) => c.day < cyc[0].day + 10 && !c.dry && c.sEnd > 0.3) : [];
    const scB = median(recent.map((c) => c.SC)) / median(base.map((c) => c.SC));
    const tB = median(recent.map((c) => c.T)) / median(base.map((c) => c.T));
    if (bigDD && Number.isFinite(scB) && Number.isFinite(tB) && day - cyc[0].day > 20 && scB < tB * 0.78) {
      const pc = Math.round((tB / scB - 1) * 100);
      F.push({
        sev: 'act', title: 'Well clogging, aquifer unchanged',
        detail: 'Drawdown per run is up ' + pc + '% more than the aquifer explains, while the refill slope holds. The loss is at the well face.',
        msg: 'clog', v: { pct: pc },
      });
    }

    if (bigDD && Number.isFinite(iR) && iR < 0.97 && Number.isFinite(sR) && sR < 0.88) {
      F.push({
        sev: 'watch', title: 'Pump delivering less water',
        detail: 'Drawdown per run down ' + Math.round((1 - sR) * 100) + '%, motor current down ' + Math.round((1 - iR) * 100) + '%. Aquifer looks unchanged.',
        msg: 'wear', v: { pct: Math.round((1 - sR) * 100) },
      });
    }

    const ie = s.interf.filter((t) => t > s.t - 5 * 24);
    if (ie.length >= 2) {
      F.push({
        sev: 'watch', title: 'Level drops while your pump is off',
        detail: ie.length + ' drops of more than 45 cm in 5 days, around ' + fmtHM(ie[ie.length - 1]) + '. A nearby borewell shares the aquifer.',
        msg: 'interf', v: { time: fmtHM(ie[ie.length - 1]) },
      });
    }

    if (day >= 267 && day <= 364) {
      let act = 0;
      let nor = 0;
      for (let d = 243; d <= day; d++) { act += s.rain[d] || 0; nor += normalRainForDay(d); }
      const pct = Math.round((act / nor) * 100);
      if (pct < 65) {
        F.push({
          sev: 'act', title: 'Weak monsoon recharge',
          detail: 'Rain since 1 Jun is ' + pct + '% of normal. Water table back only to ' + swlNow.toFixed(1) + ' m.',
          msg: 'weak', v: { pct, swl: swlNow.toFixed(1) },
        });
      }
    }

    if (fc.state === 'fail') {
      const left = fc.p50 - day;
      F.push({
        sev: left < 21 ? 'crit' : 'act', title: 'Dry before the monsoon',
        detail: 'Likely dry around ' + fmtDay(fc.p50) + '. Cut pumping ' + fc.cut + '% to reach 10 Jun.',
        msg: 'forecast', v: { rate: fc.rate.toFixed(2), date: fc.p50, cut: fc.cut },
      });
    } else if (fc.state === 'dry') {
      F.push({
        sev: 'crit', title: 'No margin left', detail: 'Peak drawdown already reaches the intake. Shorten runs now.',
        msg: 'forecast', v: { rate: (fc.rate || 0).toFixed(2), date: day, cut: 50 },
      });
    } else if (fc.state === 'ok' && fc.rate > 0.08) {
      F.push({
        sev: 'watch', title: 'Seasonal decline',
        detail: 'Falling ' + fc.rate.toFixed(2) + ' m/day. About ' + Math.max(0, fc.marginOnset).toFixed(0) + ' m to spare at the monsoon.',
        msg: 'depl', v: { rate: fc.rate.toFixed(2), margin: Math.max(0, fc.marginOnset).toFixed(0) },
      });
    }
  }

  if (!F.length) F.push({ sev: 'ok', title: 'Healthy', detail: 'Refill and drawdown look normal for the season.', msg: 'ok', v: { swl: swlNow.toFixed(1) } });
  F.sort((a, b) => SEVERITY_RANK[b.sev] - SEVERITY_RANK[a.sev]);
  s.findings = F;
}
