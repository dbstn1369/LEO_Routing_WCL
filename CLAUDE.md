# LEO_Routing_WCL — Claude Code 작업 가이드

## 활성 프로젝트 정보
- **Paper**: WCL2026-0742, "Link-Aware Routing in Multi-Tier LEO Mega-Constellations"
- **Venue**: IEEE Wireless Communications Letters (revision)
- **Git repo**: https://github.com/dbstn1369/LEO_Routing_WCL (origin/main)
- **별도 repo**: 부모 `Python Scripts/`의 git과 분리됨 (2026-05-06 init)

## 새 세션 진입 시 먼저 할 것
1. `git status` — 작업 변경사항 확인
2. `git log --oneline -5` — 최근 commit 확인
3. `git tag -l` — 롤백 가능한 안전 지점 확인
4. `HANDOFF.md` 읽기 — 직전 세션 종료 시점 컨텍스트

## 롤백 포인트
| Tag | Commit | 의미 |
|---|---|---|
| `paper-final-2026-05-06` | 5406878 | 모든 .tex paste 버전 적용 완료 + ref.bib 정리 (initial commit) |

### 롤백 명령
```bash
# 특정 태그로 복구 (변경사항 버림)
git -C "c:/Users/yoon/Documents/Python Scripts/LEO_Routing_WCL" reset --hard paper-final-2026-05-06

# 안전한 방법: 새 브랜치로 복구
git -C "c:/Users/yoon/Documents/Python Scripts/LEO_Routing_WCL" checkout -b rollback-temp paper-final-2026-05-06

# 특정 파일만 복구
git -C "c:/Users/yoon/Documents/Python Scripts/LEO_Routing_WCL" checkout paper-final-2026-05-06 -- "results/4. Simulation.tex"
```

## 디렉토리 구조
```
LEO_Routing_WCL/
├── results/                    # Paper sources (.tex, .bib) + 결과물
│   ├── main.tex
│   ├── 1. intro.tex
│   ├── 2. system model, problem.tex
│   ├── 3. algorithm.tex
│   ├── 4. Simulation.tex       # main이 input — 활성 파일
│   ├── 4.Simulation.tex        # 백업 (위와 동일 내용)
│   ├── ref.bib
│   ├── response.tex            # 리뷰어 응답
│   ├── *.csv                   # sensitivity, optimality, performance
│   └── fig*.{eps,png}          # paper figures
├── results_s1/                 # Scenario 1 결과
├── network/                    # GNN, LP solver, graph builder
├── routing/                    # algorithms, GRLR model
├── simulation/                 # evaluate.py
├── plots/                      # figure 생성 모듈
├── checkpoints/                # 학습된 GNN, GRLR 가중치
├── data/                       # TLE, position 데이터
└── run_*.py                    # 실험 스크립트
```

## 주요 스크립트
- `run_from_existing.py` — S2 메인 (기존 그래프 데이터로 routing + eval + figure)
- `run_scenario1.py` — S1 실행
- `run_optimality_real.py` — Optimality 실험 (N_PAIRS=500)
- `run_T_sensitivity.py` — T sensitivity sweep
- `run_sensitivity.py` — τ, β sensitivity sweep

## 핵심 측정값 (검증 완료, 2026-05-06)
- Sensitivity peak: τ=β=0.5, T=5min → 1.589 Gbps, 20.8% PLR
- w/o Pruning: 1.461 Gbps, 26.0% PLR (-8.8% throughput, +5.2% PLR)
- Optimality (500 pairs): N=30 → 95.7%, N=50 → 92.6%, N=70 → 93.0%
- Throughput @ 2.8G/100s: S1 vs GRLR/DR/STR = 5.4%/8.5%/12.7%, S2 = 5.5%/8.1%/12.8%
- PLR @ 2.8G/100s vs GRLR/DR/STR: S1 = 3.6/5.7/7.4%p, S2 = 3.4/5.2/7.1%p
- PLR @ 1.0G/100s vs DR/STR: S1 = 5.6/7.3%p, S2 = 5.1/6.8%p

## 작업 패턴 (사용자 선호)
- 사용자가 .tex 섹션을 paste하면서 반복 수정 요청
- placeholder/TODO 싫어함 — 측정값으로 채우기
- 변경된 부분에 `\textcolor{blue}{}` 마커 사용 (revision marking)
- "이걸로 해줘" → 바로 `results/*.tex`에 반영
- 의미 있는 수정 후 git commit + push (사용자 명시 요청, 2026-05-06)

## .gitignore 제외 파일 (push 안 됨)
- `data/position.mat` (383MB) — GitHub 100MB 제한 초과
- `results_s1/paths_graphs_s1.pkl` (102MB) — 동일
- `__pycache__/`, `*.pyc`, `*.log`

## 주의: 옆 디렉토리는 별개 프로젝트
- `../Starlink_LEO_Routing/` — 이전 제출본 (구버전), 무관
- `../LEO_Transformer_MARL/` — 다른 paper (Transformer-MADRL)
- 이 프로젝트(LEO_Routing_WCL) 작업 시 옆 디렉토리는 건드리지 않기

## 자주 쓰는 명령
```bash
# Python 환경
C:/Users/yoon/anaconda3/python.exe   # Python 3.9 (NOT Windows Store)

# 메인 실험 재실행 (~3 min)
cd "c:/Users/yoon/Documents/Python Scripts/LEO_Routing_WCL"
C:/Users/yoon/anaconda3/python.exe -u -X utf8 run_from_existing.py

# Commit + push
git add <files>
git commit -m "..."
git push
```
