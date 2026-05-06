# 다음 세션 핸드오프 프롬프트

아래 프롬프트를 복사해서 다음 세션 첫 메시지로 보내세요.

---

```
WCL2026-0742 revision 작업 중. 작업 디렉토리: c:\Users\yoon\Documents\Python Scripts\LEO_Routing_WCL

## 현재 상태 (직전 세션 종료 시점)

`results/4.Simulation.tex`와 `results/response.tex`가 최신 상태. 모든 실험 완료.

### 핵심 변경 사항 (직전 세션에서 한 일)
1. **Sensitivity figure → Table I** (교수 피드백: "공간 많이 차지함"). 컴팩트 3-column 형식 (τ, β, T 나란히).
2. **Optimality 재실험**: N_PAIRS 50 → 500. N=50 PLR 이상치 (0.5%→5.3%→1.0% 비정상 패턴) 해소됨. 새 결과: 95.7%/92.6%/93.0% (평균 93.8%).
3. **Optimality table** 컬럼 순서: Prop/Opt → **Opt/Prop** (더 좋은 값이 앞에 와서 직관적).
4. **두 단락 lab pattern 통일**:
   - Para 1 (Fig.2 duration): GRLR을 throughput과 PLR에 모두 추가 @ 100s
   - Para 2 (Fig.4 rate): PLR 비대칭 해소 — 1.0 Gbps에 PLR 추가, 2.8 Gbps에 GRLR PLR 추가
5. **Para 3 신설**: Sensitivity + w/o Pruning + Optimality 통합 한 단락
6. **response.tex**: "Fig.~5" → "Table~I" (sensitivity), "Table~I" (optimality) → "Table~II" 일괄 수정

### 핵심 측정값 (검증 완료)
- Sensitivity peak: τ=β=0.5, T=5min → 1.589 Gbps, 20.8% PLR
- w/o Pruning: 1.461 Gbps, 26.0% PLR (-8.8% throughput, +5.2% PLR)
- Optimality (500 pairs): N=30 → 95.7%, N=50 → 92.6%, N=70 → 93.0%
- PLR @ 1.0G/100s: S1 vs DR/STR = 5.6%/7.3%p, S2 = 5.1%/6.8%p
- PLR @ 2.8G/100s vs GRLR: S1 = 3.6%p, S2 = 3.4%p
- Throughput @ 2.8G/100s: S1 vs GRLR/DR/STR = 5.4%/8.5%/12.7%, S2 = 5.5%/8.1%/12.8%

### 작업 패턴
- 사용자가 보통 .tex 섹션을 다시 paste하면서 반복 수정 요청
- 사용자는 placeholder/TODO 싫어함 — 측정값으로 채워야
- 변경된 부분에는 \textcolor{blue}{} 마커 사용 (revision marking)
- 사용자가 "이걸로 해줘" 하면 바로 results/*.tex에 반영

### 메모리
직전 세션 모든 디테일은 `~/.claude/projects/c--Users-yoon-Documents-Python-Scripts/memory/project_wcl_revision.md` 참조.

### 다음 가능한 요청
- 추가 .tex 수정 (사용자가 paste)
- response.tex 추가 답변
- Cleanup: 미사용 스크립트 정리 (run_gnn_accuracy, run_gurobi_optimal, eval_gnn_per_tau, run_simulation, run_resim, plot_sensitivity_fig 등)

먼저 `results/4.Simulation.tex`와 `results/response.tex` 현재 상태 확인하고 시작.
```

---

## 추가 정보 (필요시)

### 파일 위치
- 메인 manuscript: `results/4.Simulation.tex`
- Response: `results/response.tex`
- 측정값 기록: `results/section4_values.txt`
- 핸드오프: `HANDOFF.md` (이 파일)

### 데이터 CSV
- S1: `results_s1/performance_results_s1.csv`
- S2: `results/performance_results.csv`
- Sensitivity: `results/{tau,beta,T}_sensitivity.csv`

### 자동 재현 스크립트
- `run_optimality_real.py` (N_PAIRS=500 설정됨)
- `run_T_sensitivity.py`
- `run_scenario1.py`
- `run_from_existing.py` (S2 메인)
