# 다음 세션 핸드오프 프롬프트

새 세션 첫 메시지로 아래 블록을 복사해서 붙여넣으세요.

---

```
WCL2026-0742 revision 작업 중. 작업 디렉토리:
cd "c:/Users/yoon/Documents/Python Scripts/LEO_Routing_WCL"

이 디렉토리의 CLAUDE.md를 먼저 읽고 컨텍스트 복원해줘. 아래는 직전 세션 종료 시점.

## Git 상태 (2026-05-12 기준)
- 독립 git repo: https://github.com/dbstn1369/LEO_Routing_WCL
- 안전 태그: `paper-final-2026-05-06` (initial commit 5406878) — 롤백용, 평소엔 건드리지 않음
- 이후 커밋들: figure 다듬기 + utility/box plot 작업
- 최신 HEAD 근처: `c248f0d Drop text.usetex to match plot_figures.py EPS pipeline`

## Paper .tex 상태 (모두 paste 버전 반영 완료)
- results/main.tex, 1. intro.tex, 2. system model, problem.tex, 3. algorithm.tex
- results/4. Simulation.tex (main.tex가 input하는 활성 파일) + 4.Simulation.tex (백업 동일내용)
- results/ref.bib (fu2024softact, zhang2025grlr, zhang2026anti, he2024direct 포함)
- results/response.tex (Editor + Reviewer 1~5 모두 응답 작성됨)
- abstract/intro: "average ISL utility" (per hop 빠짐)
- Sim Settings: optimality verification 방법 + Throughput/PLR 정의 명시
- 두 simulation 단락 lab pattern 통일 (GRLR 양쪽 포함), Para 3 신설 (sensitivity+pruning+optimality)
- Table I (sensitivity 3-column), Table II (optimality Opt/Prop)

## Figure 작업
- 기존 fig3_combined_box.eps (Duration+SINR 2-panel) — 그대로 보존, 롤백용
- 새 활성 figure: fig3_combined_box_l_c.eps (Duration+Capacity 2-panel, GRLR 포함)
  - 스크립트: plot_box_l_c_2panel.py
  - y축: "Avg. ISL Duration l_ij (s)" / "Avg. ISL Capacity c_ij (Gbps)" (mathtext 기호)
  - panel: (a)/(b)만 (set_xlabel + labelpad=8)
  - 폰트: Times New Roman + mathtext.fontset='stix' (text.usetex=False — EPS bbox 정상화 위해)
- 또 다른 백업: plot_utility_box_3panel.py + fig3_combined_box_3panel — Duration+SINR+U_ij 3-panel (사용자가 빼라고 해서 inactive)

## 측정 데이터 (검증 완료)
- Sensitivity: τ=β=0.5, T=5min → 1.589 Gbps, 20.8% PLR
- w/o Pruning: 1.461 Gbps, 26.0% PLR (-8.8% Thr, +5.2% PLR)
- Optimality (500 pairs): N=30/50/70 → 95.7/92.6/93.0%
- Throughput @ 2.8G/100s vs GRLR/DR/STR: S1=5.4/8.5/12.7%, S2=5.5/8.1/12.8%
- PLR @ 2.8G/100s vs GRLR/DR/STR: S1=3.6/5.7/7.4%p, S2=3.4/5.2/7.1%p

## Path 평균 통계 (fig3_combined_box_l_c.eps에 사용)
- Proposed: l=78.4s, c=2.48 Gbps, U_ij=0.131
- GRLR:     l=53.9s, c=2.42 Gbps, U_ij=0.090
- DR:       l=44.1s, c=2.42 Gbps, U_ij=0.074
- STR:      l=38.9s, c=2.34 Gbps, U_ij=0.065
(U_ij는 paper Eq.(11) strict softmax over E, beta=0.5, T=300s)

## 시뮬레이션 길이 (R2 C4 답변용)
- N_CYCLES=80, SNAPSHOT_INTERVAL_S=300
- 총 400분 ≈ 6.7시간
- LEO orbital period ≈ 95분 (400-600km)
- ~4.2 orbital periods cover

## 최근 결정 (2026-05-12)
1. **Utility 표 paper 삽입**: ❌ **안 하기로 결정**
2. **R2 C4 본문 한 줄 추가 (orbital periods)**: ❌ **안 넣기로 결정** (response.tex에만 반영, 4.Simulation.tex 본문은 그대로)

→ Revision 본문(.tex) 작업 **일단 완료 상태**. 모든 수치 CSV와 검증됨 (raw measurement, calibrated evaluate.py 기준).

## 결과 격차 분석 (참고)
- 제출본 figure는 일부 manual edited CSV 기준 → 그래서 격차가 더 커 보임
- 현재 revision은 raw 측정 결과 그대로 사용 → 정직, sensitivity/optimality table 절대값과 일관
- 절대 격차(Thr, PLR pp)는 제출본과 비슷하거나 일부 더 큼; percentage가 작아 보이는 건 baseline absolute Thr 상승 효과
- 결정: raw 유지 + figure visual 튜닝 안 함 (reproducibility + reviewer 검증 신뢰도 우선)

## 가능한 다음 작업
- Revision 제출 후 reviewer 후속 round 대응
- 그 외에는 본문/figure/response 수정 사항 없음

## 작업 패턴 (사용자 선호)
- .tex paste-iterate 패턴
- placeholder 싫어함, 측정값으로 채우기
- \textcolor{blue}{} 마커로 revision 표시
- 의미 있는 수정 후 git commit + push 자동
- 기존 코드 안 건드리고 새 파일로 (롤백 쉽게)
- 한국어 사용자/조안나(공저자) iterative 피드백 흐름

먼저 `git status`, `git log --oneline -5`, `git tag -l` 확인하고 시작.
```

---

## 롤백 가이드 (변경 망쳤을 때)

### 안전 태그로 즉시 복구
```bash
cd "c:/Users/yoon/Documents/Python Scripts/LEO_Routing_WCL"

# 옵션 1: 모든 변경 버리고 paper-final로
git reset --hard paper-final-2026-05-06

# 옵션 2: 새 브랜치로 안전하게 복구 (현재 변경 보존)
git checkout -b rollback-attempt paper-final-2026-05-06

# 옵션 3: 특정 파일만 되돌리기
git checkout paper-final-2026-05-06 -- "results/4. Simulation.tex"
```

### 새 안전 지점 만들기
의미 있는 수정 후, 다음 롤백 포인트 만들기:
```bash
git tag -a paper-vN-YYYY-MM-DD -m "<설명>"
git push origin paper-vN-YYYY-MM-DD
```

---

## 추가 정보

### 파일 위치
- main.tex가 input하는 활성 파일: `results/4. Simulation.tex` (공백 있음)
- 백업 동일 파일: `results/4.Simulation.tex` (공백 없음)
- Response: `results/response.tex`
- 측정값 기록: `results/section4_values.txt`

### 데이터 CSV
- S1: `results_s1/performance_results_s1.csv`
- S2: `results/performance_results.csv`
- Sensitivity: `results/{tau,beta,T}_sensitivity.csv`

### 메모리 (영구)
- `~/.claude/projects/c--Users-yoon-Documents-Python-Scripts/memory/MEMORY.md` — 인덱스
- `project_wcl_revision.md` — 프로젝트 디테일
- `feedback_git_versioning.md` — "수정 후 commit/push" feedback
