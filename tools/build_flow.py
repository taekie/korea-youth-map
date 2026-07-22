#!/usr/bin/env python3
"""KOSIS 시군구 OD → 지도용 flow JSON.

중심좌표는 넣지 않는다. flow.html에서 d3.geoPath().centroid()로 런타임 계산해
기존 지도(geoMercator fitExtent)와 자동으로 정합시키기 위함이다.

출력 flow_2025.json
  regions: [[sido, name], ...]           geojson과 같은 순서로 맞춘 인덱스
  flows:   [[o, d, total, male], ...]    d의 여자 = total - male
"""
import csv, collections, json, sys

YEAR = sys.argv[1] if len(sys.argv) > 1 else "2025"
GEO = "/Users/taekie/claudecode/korea-youth-map/sigungu_pop.geojson"
MIN_FLOW = 5   # 5명 미만 흐름은 지도에서 의미가 없어 버린다

SIDO = {'11':'서울','26':'부산','27':'대구','28':'인천','29':'광주','30':'대전','31':'울산',
        '36':'세종','41':'경기','43':'충북','44':'충남','46':'전남','47':'경북','48':'경남',
        '50':'제주','51':'강원','52':'전북'}

import re

ALIAS = {('세종', '세종시'): ('세종', '세종특별자치시')}


def node_key(sido, name):
    """지도는 일반구(수원시장안구), KOSIS는 시(수원시) 단위 → 시로 통합."""
    if (sido, name) in ALIAS:
        return ALIAS[(sido, name)]
    m = re.match(r'^(.+?시)[가-힣]+구$', name)
    return (sido, m.group(1)) if m else (sido, name)


geo = json.load(open(GEO))
feats = [(f['properties']['sido'], f['properties']['name'].replace(' ', ''))
         for f in geo['features']]

# 흐름 노드 = 시 단위. members는 노드에 속한 geojson feature 인덱스.
regions, members, idx = [], [], {}
for i, (s, n) in enumerate(feats):
    k = node_key(s, n)
    if k not in idx:
        idx[k] = len(regions)
        regions.append(k)
        members.append([])
    members[idx[k]].append(i)
print(f'geojson {len(feats)}개 폴리곤 → 흐름 노드 {len(regions)}개')

rows = [r for r in csv.DictReader(open(f'od_sgg_{YEAR}.csv'))
        if len(r['C1']) == 5 and len(r['C2']) == 5 and r['C3'] in ('0', '1')]

# 코드별 2025년 총 이동량 — 0이면 폐지된 옛 행정구역이므로 제외
live = collections.Counter()
for r in rows:
    if r['C3'] == '0':
        v = int(r['DT']); live[r['C1']] += v; live[r['C2']] += v

name = {}
for r in rows:
    name[r['C1']] = r['C1_NM'].replace(' ', '')
    name[r['C2']] = r['C2_NM'].replace(' ', '')

# KOSIS 코드 → geojson 인덱스
code2i, unmatched = {}, []
for c, n in sorted(name.items()):
    if live[c] == 0:
        continue                       # 옛 행정구역(값 0)
    key = (SIDO.get(c[:2], '?'), n)
    if key in idx:
        code2i[c] = idx[key]
    else:
        unmatched.append((c, key, live[c]))

print(f'매칭 {len(code2i)}/{len(regions)}개  ·  미매칭 {len(unmatched)}개')
for c, k, v in unmatched:
    print(f'  미매칭 {c} {k} (이동량 {v:,})')
covered = {code2i[c] for c in code2i}
for i, r in enumerate(regions):
    if i not in covered:
        print(f'  지도에만 있음: {r}')

# 흐름 집계
tot = collections.defaultdict(int); male = collections.defaultdict(int)
for r in rows:
    o, d = code2i.get(r['C1']), code2i.get(r['C2'])
    if o is None or d is None or o == d:
        continue
    v = int(r['DT'])
    (tot if r['C3'] == '0' else male)[(o, d)] += v

flows = [[o, d, t, male.get((o, d), 0)] for (o, d), t in sorted(tot.items()) if t >= MIN_FLOW]
dropped = sum(t for (o, d), t in tot.items() if t < MIN_FLOW)
print(f'흐름 {len(flows):,}개 (총 {sum(f[2] for f in flows):,}명, '
      f'{MIN_FLOW}명 미만 {dropped:,}명 제외)')

out = dict(year=int(YEAR), regions=[list(r) for r in regions],
           members=members, flows=flows)
path = f'flow_{YEAR}.json'
json.dump(out, open(path, 'w'), ensure_ascii=False, separators=(',', ':'))
import os
print(f'→ {path}  {os.path.getsize(path)/1e6:.2f}MB')
