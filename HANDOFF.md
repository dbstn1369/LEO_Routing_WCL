# 다음 세션 핸드오프 프롬프트

새 세션 첫 메시지로 아래 블록을 복사해서 붙여넣으세요.

---

```
WCL2026-0742 revision 작업 중. 작업 디렉토리 진입:
cd "c:/Users/yoon/Documents/Python Scripts/LEO_Routing_WCL"

이 디렉토리의 CLAUDE.md를 먼저 읽고 컨텍스트 복원해줘.

## 직전 세션 종료 시점 (2026-05-06)

### Git 상태
- 별도 git repo (https://github.com/dbstn1369/LEO_Routing_WCL)
- HEAD = `5406878` "Initial commit: WCL2026-0742 revision project"
- 안전 태그: `paper-final-2026-05-06` (전체 paste 버전 적용 완료 시점)

### 무엇이 적용되어 있나
- 모든 .tex (main, intro, system model, algorithm, simulation) 최신 paste 버전 반영
- ref.bib에 `fu2024softact` 추가
- abstract/intro: "average ISL utility" (per hop 표현 제거)
- Sim Settings: optimality verification 방법 + Throughput/PLR 정의 추가
- 두 simulation 단락 lab pattern 통일 (GRLR 양쪽 paragraph에 포함)
- Para 3 (sensitivity + w/o pruning + optimality 통합)
- Table I (sensitivity 3-column), Table II (optimality Opt/Prop 컬럼순)

### 핵심 측정값 (검증됨)
- Sensitivity peak: τ=β=0.5, T=5min → 1.589 Gbps, 20.8% PLR
- w/o Pruning: 1.461 Gbps, 26.0% PLR
- Optimality (500 pairs): N=30/50/70 → 95.7/92.6/93.0%
- Throughput @ 2.8G/100s vs GRLR/DR/STR: S1=5.4/8.5/12.7%, S2=5.5/8.1/12.8%
- PLR @ 2.8G/100s vs GRLR/DR/STR: S1=3.6/5.7/7.4%p, S2=3.4/5.2/7.1%p

### 작업 패턴
- .tex paste-iterate 패턴 (사용자 paste → 수정 반영)
- placeholder 싫어함 — 측정값으로 채우기
- `\textcolor{blue}{}` 마커로 revision 표시
- 의미 있는 수정 후 git commit + push (자동으로)

### 가능한 다음 요청
- 추가 .tex 수정 (paste 형태로)
- response.tex 리뷰어 답변 추가
- Cleanup: 미사용 스크립트 (run_gnn_accuracy, run_gurobi_optimal, eval_gnn_per_tau, run_simulation, run_resim, plot_sensitivity_fig 등)
- 새 figure 생성

먼저 `git status`와 `git log --oneline -3` 확인하고 시작.
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
