/**
 * Sparkline finite-point harden — empty / NaN / ±Inf must not plot.
 *
 * Invoked from web/ (cwd + module root):
 *   pytest tests/test_web_route_regressions.py::test_sparkline_finite_points_unit
 */
import { finiteSparklinePoints } from "./src/lib/sparkline.ts";

function fail(msg: string): never {
  console.error(`FAIL: ${msg}`);
  process.exit(1);
}

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) fail(msg);
}

function testDropsNonFiniteAndEmpty(): void {
  assert(finiteSparklinePoints([]).length === 0, "empty in → empty out");
  assert(
    finiteSparklinePoints([{ ts: null, price: null }]).length === 0,
    "null price dropped",
  );
  assert(
    finiteSparklinePoints([{ ts: "t", price: Number.NaN }]).length === 0,
    "NaN dropped",
  );
  assert(
    finiteSparklinePoints([{ ts: "t", price: Number.POSITIVE_INFINITY }]).length ===
      0,
    "+Inf dropped",
  );
  assert(
    finiteSparklinePoints([{ ts: "t", price: Number.NEGATIVE_INFINITY }]).length ===
      0,
    "-Inf dropped",
  );
  // One finite among junk → still below sparkline threshold of 2.
  const mixed = finiteSparklinePoints([
    { ts: "a", price: null },
    { ts: "b", price: Number.NaN },
    { ts: "c", price: 12.5 },
    { ts: "d", price: Number.POSITIVE_INFINITY },
  ]);
  assert(mixed.length === 1, `expected 1 finite, got ${mixed.length}`);
  assert(mixed[0].price === 12.5, "kept finite price");
  assert(mixed.length < 2, "mixed junk stays below empty threshold");
}

function testKeepsFiniteSeries(): void {
  const pts = finiteSparklinePoints([
    { ts: "2026-01-01T00:00:00Z", price: 10 },
    { ts: "2026-01-01T00:01:00Z", price: 0 },
    { ts: "2026-01-01T00:02:00Z", price: -1.5 },
  ]);
  assert(pts.length === 3, `expected 3, got ${pts.length}`);
  assert(pts[0].price === 10 && pts[1].price === 0 && pts[2].price === -1.5, "order");
  assert(pts.every((p) => Number.isFinite(p.price)), "all finite");
}

function testRejectsNonNumberPrimitives(): void {
  const sneaky = finiteSparklinePoints([
    { ts: "t", price: "12" as unknown as number },
    { ts: "t", price: undefined },
    { ts: "t", price: true as unknown as number },
  ]);
  assert(sneaky.length === 0, "string/undefined/bool must not coerce");
}

testDropsNonFiniteAndEmpty();
testKeepsFiniteSeries();
testRejectsNonNumberPrimitives();
console.log("WEB_SPARKLINE_FINITE_UNIT_OK");
