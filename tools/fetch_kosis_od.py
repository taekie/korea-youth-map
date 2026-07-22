#!/usr/bin/env python3
"""KOSIS 국내인구이동통계 OD(전출지→전입지) 수집.

표
  DT_1B26003_A02  전출지/전입지(시군구)/성별   2012~   274x274x3, 연령 없음
  DT_1B26003      전출지/전입지(시도)/성/연령  1970~   18x18x3x18

C1=전출지, C2=전입지, C3=성별, C4=연령(시도표만). 코드길이 2=시도, 5=시군구.
objL1은 다중코드를 받지 않으므로(err 21) 시군구표는 전출지 1개씩 루프한다.

사용
  export KOSIS_API_KEY=...
  python3 fetch_kosis_od.py --year 2025
"""
import argparse, csv, json, os, re, subprocess, sys, time, urllib.parse

BASE = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
META = "https://kosis.kr/openapi/statisticsData.do"
KEY = os.environ.get("KOSIS_API_KEY", "")
COLS = ["PRD_DE", "C1", "C1_NM", "C2", "C2_NM", "C3", "C3_NM", "C4", "C4_NM", "DT"]


def _get(url, tries=3):
    """샌드박스 프록시의 self-signed 인증서 때문에 urllib 대신 curl을 쓴다."""
    for i in range(tries):
        p = subprocess.run(["curl", "-s", "-m", "180", url], capture_output=True)
        raw = p.stdout.decode("utf-8", "replace")
        if p.returncode == 0 and raw:
            break
        if i == tries - 1:
            raise RuntimeError(f"curl 실패 rc={p.returncode}")
        time.sleep(3 * (i + 1))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(re.sub(r'([{,])\s*([A-Za-z_]\w*)\s*:', r'\1"\2":', raw))


def fetch(tbl, year, **objs):
    q = dict(method="getList", apiKey=KEY, format="json", jsonVD="Y", orgId="101",
             tblId=tbl, itmId="T70", prdSe="Y", startPrdDe=str(year), endPrdDe=str(year))
    q.update(objs)
    d = _get(BASE + "?" + urllib.parse.urlencode(q))
    if isinstance(d, dict):
        raise RuntimeError(f"KOSIS {d.get('err')}: {d.get('errMsg')}")
    return d


def codes(tbl, year, **objs):
    """C1 분류코드 목록을 얻기 위한 최소 조회."""
    return sorted({(r["C1"], r["C1_NM"]) for r in fetch(tbl, year, **objs)})


def write(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    mb = os.path.getsize(path) / 1e6
    print(f"  → {os.path.basename(path)}  {len(rows):,}행  {mb:.1f}MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--which", choices=["sgg", "sido", "both"], default="both")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    if not KEY:
        sys.exit("KOSIS_API_KEY 가 비어 있습니다.")

    if a.which in ("sido", "both"):
        print(f"[sido] 전출지/전입지(시도)/성/연령 {a.year}년")
        rows = fetch("DT_1B26003", a.year, objL1="ALL", objL2="ALL", objL3="ALL", objL4="ALL")
        write(rows, os.path.join(a.out, f"od_sido_{a.year}.csv"))

    if a.which in ("sgg", "both"):
        print(f"[sgg] 전출지/전입지(시군구)/성별 {a.year}년")
        origins = codes("DT_1B26003_A02", a.year, objL1="ALL", objL2="00", objL3="0")
        print(f"  전출지 {len(origins)}개 — 순차 수집")
        rows, t0 = [], time.time()
        for i, (c, nm) in enumerate(origins, 1):
            rows += fetch("DT_1B26003_A02", a.year, objL1=c, objL2="ALL", objL3="ALL")
            if i % 25 == 0 or i == len(origins):
                print(f"  {i}/{len(origins)}  {nm}  누적 {len(rows):,}행  {time.time()-t0:.0f}s")
        write(rows, os.path.join(a.out, f"od_sgg_{a.year}.csv"))


if __name__ == "__main__":
    main()
