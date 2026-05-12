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

## 진행 중인 작업 (사용자 결정 대기)
1. **Utility 표 paper 삽입**: paper Eq strict softmax 결과(Proposed=0.131, GRLR=0.090, DR=0.074, STR=0.065)를 표로.
   - 형식 A (compact, U_ij 1행) vs 형식 B (l/c/U 3행)
   - 위치: 4.Simulation.tex (paper main) vs response.tex (Reviewer 1 Comment 1)
2. **R2 C4 (orbital periods) 응답 보강**:
   - 권장 답변 작성됨 (3-part: total 400min/6.7h, ~4 orbital periods cover, TLE 주기 반복으로 GNN input 분포 일정)
   - response.tex에는 이미 반영 완료 — 4.Simulation.tex에도 "covers ~80 snapshots, ~6.7h, ~4 orbital periods" 한 줄 추가할지 결정 필요

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
