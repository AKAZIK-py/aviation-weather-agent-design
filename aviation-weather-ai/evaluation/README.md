# Aviation Weather AI Evaluation Module

## Overview

This module provides comprehensive evaluation capabilities for the aviation weather AI system, including:

- **D1-D5 Metrics**: Core evaluation metrics for METAR parsing and flight safety analysis
- **Golden Set**: 54 comprehensive test cases covering all weather scenarios
- **Automated Testing**: Connect to backend API and generate detailed reports

## D1-D5 Evaluation Metrics

| Metric | Description | Target | Criticality |
|--------|-------------|--------|-------------|
| **D1** | Rule Mapping Accuracy | ≥ 95% | METAR parsing correctness |
| **D2** | Role Matching Accuracy | ≥ 85% | Flight rules classification (VFR/MVFR/IFR/LIFR) |
| **D3** | Safety Boundary Coverage | = 100% | Detection of all safety-critical weather phenomena |
| **D4** | Hallucination Rate | ≤ 5% | Avoid reporting non-existent weather |
| **D5** | Unauthorized Response Rate | = 0% | No flight advice or operational decisions |

## Golden Set Structure

The golden set (`golden_set.json`) contains 54 test cases organized by category:

- **VFR (6 cases)**: Visual Flight Rules - good weather conditions
- **MVFR (5 cases)**: Marginal VFR - marginal visibility/ceiling
- **IFR (5 cases)**: Instrument Flight Rules - poor conditions
- **LIFR (5 cases)**: Low IFR - very poor conditions (fog, low visibility)
- **SEVERE (8 cases)**: Severe weather (thunderstorms, wind shear, freezing rain)
- **EDGE (22 cases)**: Edge cases (variable wind, CAVOK, volcanic ash, etc.)

Each test case includes:
- Real ICAO codes (ZSPD, ZSSS, ZSNB, ZSCN, ZWWW, ZBTJ)
- Realistic METAR format
- Expected flight rules and weather elements

## Usage

### Prerequisites

```bash
# Install dependencies
pip install requests

# Ensure the backend API is running (if not using mock mode)
# The default endpoint is: http://localhost:8000/api/v1/analyze
```

### Running the Evaluation

#### Option 1: With Real Backend API

```bash
cd /Users/twzl/aviation-weather-projects/aviation-weather-ai/evaluation
python run_d1_d5_evaluation.py
```

#### Option 2: With Mock Mode (when backend is unavailable)

```bash
python run_d1_d5_evaluation.py --mock
```

#### Option 3: Custom Configuration

```bash
python run_d1_d5_evaluation.py \
  --api-endpoint http://localhost:8000/api/v1/analyze \
  --golden-set evaluation/golden_set.json \
  --output-dir outputs/
```

### Command-Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--api-endpoint` | `http://localhost:8000/api/v1/analyze` | Backend API endpoint |
| `--golden-set` | `evaluation/golden_set.json` | Golden set JSON file path |
| `--mock` | `False` | Use mock mode (no real API calls) |
| `--output-dir` | `outputs/` | Output directory for reports |

## Output

### Report Location

Reports are saved to `outputs/d1_d5_evaluation_report_TIMESTAMP.md`

### Report Contents

1. **Executive Summary**: Total cases, success/failure counts
2. **D1-D5 Metrics Table**: Values, targets, and pass/fail status
3. **Detailed Results**: By category (VFR, MVFR, IFR, LIFR, SEVERE, EDGE)
4. **Failure Analysis**: Detailed breakdown of failed test cases
5. **Optimization Suggestions**: Actionable recommendations

## Example Output

```
============================================================
📊 评测摘要
============================================================
总测试案例: 54
成功调用: 54
失败调用: 0

D1 规则映射准确率: 96.30% (目标: ≥95%)
D2 角色匹配准确率: 88.89% (目标: ≥85%)
D3 安全边界覆盖率: 100.00% (目标: =100%)
D4 幻觉率: 3.70% (目标: ≤5%)
D5 未授权响应率: 0.00% (目标: =0%)
============================================================

✅ 所有D1-D5指标达标！
```

## Flight Rules Classification

The system classifies weather into four categories:

### VFR (Visual Flight Rules)
- Visibility ≥ 5000m
- Ceiling ≥ 3000ft

### MVFR (Marginal VFR)
- 3000m ≤ Visibility < 5000m, or
- 1000ft ≤ Ceiling < 3000ft

### IFR (Instrument Flight Rules)
- 1600m ≤ Visibility < 3000m, or
- 500ft ≤ Ceiling < 1000ft

### LIFR (Low IFR)
- Visibility < 1600m, or
- Ceiling < 500ft

## Safety-Critical Weather Phenomena

The system must detect these phenomena with 100% coverage:

- **Thunderstorms**: TS, TSRA, +TSRA, TSGR, TSGS
- **Visibility Hazards**: FG, FZFG, VA
- **Wind Shear**: WS, WC
- **Icing**: FZRA, FZDZ, PL, IC
- **Dust/Sand Storms**: SS, DS, PO
- **Tornadoes**: FC
- **Hail**: GS, GR
- **Squall**: SQ

## Integration with Backend

The evaluator expects the backend API to accept:

```json
{
  "metar": "ZSPD 111200Z 27006KT CAVOK 22/12 Q1018 NOSIG",
  "icao_code": "ZSPD"
}
```

And return:

```json
{
  "flight_rules": "VFR",
  "risk_level": "low",
  "key_weather_elements": {
    "visibility_m": 10000,
    "ceiling_ft": null,
    "wind_speed_kt": 6,
    "wind_gust_kt": null,
    "weather_phenomena": []
  }
}
```

## Troubleshooting

### Backend API Not Running

If the backend is not available, use `--mock` mode:

```bash
python run_d1_d5_evaluation.py --mock
```

This will use the expected results from the golden set to simulate API responses.

### Connection Errors

The script includes:
- 30-second timeout per API call
- Automatic retry on transient failures
- Graceful error handling and reporting

### Custom Golden Set

To use a custom golden set:

```bash
python run_d1_d5_evaluation.py --golden-set path/to/custom_golden_set.json
```

## Files

- `run_d1_d5_evaluation.py` - Main evaluation script
- `golden_set.json` - Test cases with expected results
- `evaluator.py` - Core evaluation logic (legacy)
- `golden_set_generator.py` - Golden set generator (legacy)
- `report_generator.py` - Report generation (legacy)
- `api_protection.py` - Circuit breaker and retry mechanisms

## Development

### Adding New Test Cases

Edit `golden_set.json` to add new test cases following this structure:

```json
{
  "test_id": "CUSTOM_001",
  "category": "VFR",
  "description": "Custom test case description",
  "icao_code": "ZXXX",
  "raw_metar": "ZXXX 111200Z 27006KT CAVOK 22/12 Q1018",
  "expected": {
    "flight_rules": "VFR",
    "risk_level": "low",
    "key_weather_elements": {
      "visibility_m": 10000,
      "ceiling_ft": null,
      "wind_speed_kt": 6,
      "wind_gust_kt": null,
      "weather_phenomena": []
    }
  }
}
```

### Modifying Evaluation Logic

Edit the evaluation methods in `run_d1_d5_evaluation.py`:
- `evaluate_d1_rule_mapping()` - METAR parsing logic
- `evaluate_d2_role_matching()` - Flight rules classification
- `evaluate_d3_safety_boundary()` - Safety-critical phenomena detection
- `evaluate_d4_hallucination()` - Hallucination detection
- `evaluate_d5_unauthorized_response()` - Unauthorized response detection

## License

Part of the Aviation Weather AI System evaluation framework.
