import { mergeObjects } from "../../objects";
import { cumulativeSum } from "../../math";
import dayjs from "dayjs";

// Hall of Heroes chart: gold, silver and bronze lead; everyone else is a faint line.
const MEDALS = ["#e8c77e", "#c9d1d6", "#c0874a"];
const FAINT = "rgba(244, 236, 220, 0.22)";
const INK = "rgba(244, 236, 220, 0.55)";
const css = (name, fallback) =>
  (typeof document !== "undefined" &&
    getComputedStyle(document.documentElement).getPropertyValue(name).trim()) ||
  fallback;
const SERIF = "'Voyage Serif', 'Cormorant Garamond', Georgia, serif";
// Marcellus has lining figures, so numbers read evenly on the canvas
const NUM = "'Voyage Display', Marcellus, Georgia, serif";

function scoreAt(points, t) {
  let s = 0;
  for (const [time, score] of points) {
    if (+time <= t) s = score;
    else break;
  }
  return s;
}

export function getOption(mode, places, optionMerge) {
  const GOLD = css("--acc", "#d9b56b");
  const ACC_RGB = css("--acc-rgb", "217, 181, 107");
  const teams = Object.keys(places);
  const tracks = teams.map(key => {
    const solves = places[key]["solves"];
    const totals = cumulativeSum(solves.map(s => s.value));
    return {
      name: places[key]["name"],
      points: solves.map((s, i) => [dayjs(s.date).toDate(), totals[i]]),
    };
  });

  const narrow = typeof window !== "undefined" && window.innerWidth < 640;

  let option = {
    backgroundColor: "transparent",
    textStyle: { color: INK, fontFamily: SERIF },
    animationDuration: 2200,
    animationEasing: "cubicOut",
    grid: { left: 8, right: narrow ? 44 : 150, top: 24, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(10, 9, 7, 0.96)",
      borderColor: `rgba(${ACC_RGB}, 0.45)`,
      borderWidth: 1,
      padding: [10, 14],
      extraCssText: "border-radius: 12px; box-shadow: 0 12px 30px rgba(0,0,0,0.6);",
      axisPointer: {
        type: "line",
        lineStyle: { color: `rgba(${ACC_RGB}, 0.45)`, type: "dashed" },
      },
      formatter: params => {
        const t = +params[0].axisValue;
        const rows = tracks
          .map((tr, i) => ({
            name: tr.name,
            score: scoreAt(tr.points, t),
            color: MEDALS[i] || "#f4ecdc",
          }))
          .sort((a, b) => b.score - a.score)
          .slice(0, 10);
        const head = `<div style="font-family:${SERIF};font-size:12px;letter-spacing:.2em;text-transform:uppercase;color:${GOLD};margin-bottom:6px">${dayjs(t).format("MMM D · HH:mm")}</div>`;
        const body = rows
          .map(
            (r, i) =>
              `<div style="display:flex;justify-content:space-between;gap:24px;font-family:${SERIF};font-size:15px;line-height:1.55;color:#f4ecdc">` +
              `<span><span style="display:inline-block;width:20px;color:${r.color};font-variant-numeric:lining-nums">${i + 1}</span>${r.name}</span>` +
              `<span style="color:${r.color === "#f4ecdc" ? "#f1d79c" : r.color};font-variant-numeric:lining-nums tabular-nums">${r.score}</span></div>`,
          )
          .join("");
        return head + body;
      },
    },
    // ctrl/cmd + scroll zooms; plain scrolling scrolls the page
    dataZoom: [
      {
        type: "inside",
        xAxisIndex: [0],
        zoomOnMouseWheel: "ctrl",
        moveOnMouseWheel: false,
        moveOnMouseMove: true,
      },
    ],
    xAxis: [
      {
        type: "time",
        boundaryGap: false,
        splitNumber: narrow ? 3 : 6,
        axisLine: { lineStyle: { color: `rgba(${ACC_RGB}, 0.3)` } },
        axisTick: { show: false },
        axisLabel: {
          color: INK,
          fontFamily: NUM,
          fontSize: 12,
          hideOverlap: true,
          formatter: {
            year: "{yyyy}",
            month: "{MMM}",
            day: "{MMM} {d}",
            hour: "{HH}:{mm}",
            minute: "{HH}:{mm}",
          },
        },
        splitLine: { show: false },
      },
    ],
    yAxis: [
      {
        type: "value",
        min: 0,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: INK, fontFamily: NUM, fontSize: 12 },
        splitLine: { lineStyle: { color: `rgba(${ACC_RGB}, 0.1)`, type: [2, 6] } },
      },
    ],
    series: [],
  };

  tracks.forEach((tr, i) => {
    const medal = MEDALS[i];
    const color = medal || FAINT;
    option.series.push({
      name: tr.name,
      type: "line",
      data: tr.points,
      smooth: 0.35,
      smoothMonotone: "x",
      showSymbol: false,
      symbol: "circle",
      symbolSize: 6,
      z: medal ? 10 - i : 1,
      lineStyle: {
        width: medal ? 2.6 : 1.3,
        color,
        shadowBlur: medal ? 12 : 0,
        shadowColor: medal ? medal + "88" : "transparent",
      },
      itemStyle: { color: medal || "#f4ecdc" },
      areaStyle:
        i === 0
          ? {
              color: {
                type: "linear",
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: "rgba(232, 199, 126, 0.20)" },
                  { offset: 1, color: "rgba(232, 199, 126, 0)" },
                ],
              },
            }
          : undefined,
      endLabel: {
        show: !narrow || Boolean(medal),
        distance: 10,
        fontFamily: SERIF,
        fontSize: medal ? 14 : 12,
        color: medal || "rgba(244, 236, 220, 0.45)",
        formatter: p =>
          narrow ? `{s|${p.value[1]}}` : `{n|${p.seriesName}}  {s|${p.value[1]}}`,
        rich: {
          n: {
            fontFamily: SERIF,
            fontSize: medal ? 14 : 12,
            color: medal || "rgba(244, 236, 220, 0.45)",
          },
          s: {
            fontFamily: NUM,
            fontSize: medal ? 12 : 11,
            color: medal || "rgba(244, 236, 220, 0.45)",
          },
        },
      },
      labelLayout: { moveOverlap: "shiftY" },
      emphasis: { disabled: true },
      // the leader's line is drawn last, like the final leg of the voyage
      animationDelay: (tracks.length - 1 - i) * 140,
    });
  });

  if (optionMerge) {
    option = mergeObjects(option, optionMerge);
  }
  return option;
}
