# Aviation Weather Agent Tests

Comprehensive pytest test suite for the aviation weather analysis agent.

## Test Structure

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── test_parse_metar.py         # METAR parsing tests
├── test_risk_assessor.py       # Risk assessment tests
├── test_safety_checker.py      # Safety boundary check tests
├── test_api_integration.py     # API endpoint integration tests
└── README.md                   # This file
```

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_parse_metar.py
```

### Run Specific Test Class

```bash
pytest tests/test_parse_metar.py::TestMETARParser
```

### Run Specific Test

```bash
pytest tests/test_parse_metar.py::TestMETARParser::test_parse_vfr_weather
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage Report

```bash
pytest --cov=app --cov-report=html
```

Then open `htmlcov/index.html` in your browser.

### Run Only Unit Tests

```bash
pytest -m unit
```

### Run Only Integration Tests

```bash
pytest -m integration
```

### Run Async Tests Only

```bash
pytest -m asyncio
```

### Run Tests in Parallel

```bash
pytest -n auto  # Requires pytest-xdist
```

## Test Categories

### 1. METAR Parsing Tests (`test_parse_metar.py`)

Tests for the `METARParser` class:
- ✅ Basic parsing (VFR/IFR/LIFR)
- ✅ Wind speed and direction
- ✅ Visibility (meters/statute miles/CAVOK)
- ✅ Temperature (positive/negative/mixed)
- ✅ Cloud layers (single/multiple/CB towers)
- ✅ Weather phenomena (thunderstorm/rain/fog/haze)
- ✅ Flight rules calculation (VFR/MVFR/IFR/LIFR)
- ✅ Edge cases (empty/malformed/partial METAR)
- ✅ Real-world METAR examples

### 2. Risk Assessment Tests (`test_risk_assessor.py`)

Tests for the `RiskAssessor` class:
- ✅ Wind speed risk (LOW/MEDIUM/HIGH/CRITICAL thresholds)
- ✅ Visibility risk (good/moderate/poor/critical)
- ✅ Cloud height risk
- ✅ Weather phenomena risk (thunderstorm/ice/fog)
- ✅ Role-specific weights (pilot/dispatcher/ground_crew/forecaster)
- ✅ Combined risk factors
- ✅ Boundary value testing
- ✅ Integration scenarios

### 3. Safety Checker Tests (`test_safety_checker.py`)

Tests for the `SafetyChecker` class:
- ✅ CRITICAL risk intervention (mandatory)
- ✅ IFR/LIFR weather checks
- ✅ Thunderstorm detection
- ✅ Low visibility (<800m) checks
- ✅ Strong wind (>30KT) checks
- ✅ Freezing conditions (FZRA/FZFG)
- ✅ Role-specific safety rules
- ✅ Multiple violations handling
- ✅ D3 metric: Safety boundary = 100%

### 4. API Integration Tests (`test_api_integration.py`)

Tests for FastAPI endpoints:
- ✅ `/analyze` endpoint (METAR analysis)
- ✅ `/health` endpoint (health check)
- ✅ `/airports` endpoint (airport list)
- ✅ `/metrics` endpoint (service metrics)
- ✅ Request/response validation
- ✅ Error handling (400/422/500/503)
- ✅ Mock LLM client and METAR fetcher
- ✅ Performance tests (response time/concurrent requests)

## Test Data

### Sample METAR Strings

```python
# VFR good weather
"METAR ZSPD 110800Z 25012KT 9999 SCT040 28/22 Q1008"

# IFR low visibility
"METAR ZSSS 110830Z 18008KT 0800 FG VV002 10/09 Q1013"

# LIFR extreme conditions
"METAR ZSNJ 110900Z 24015G25KT 0400 FG VV001 08/07 Q1015"

# Thunderstorm
"METAR ZSHC 110845Z 27018G30KT 4000 +TSRA BKN010CB 25/23 Q1005"

# Strong wind
"METAR ZSNB 110915Z 32035G45KT 9999 SCT050 15/08 Q1018"

# Freezing conditions
"METAR ZSWZ 110930Z 05010KT 2000 FZFG OVC003 M02/M04 Q1020"

# CAVOK
"METAR ZSSS 111030Z 35006KT CAVOK 22/15 Q1022"
```

### Test Fixtures

All fixtures are defined in `conftest.py`:

- `sample_metar_vfr` - VFR weather example
- `sample_metar_ifr` - IFR weather example
- `sample_metar_lifr` - LIFR weather example
- `sample_metar_thunderstorm` - Thunderstorm weather
- `sample_metar_strong_wind` - Strong wind weather
- `sample_metar_freezing` - Freezing conditions
- `parsed_metar_good` - Parsed good weather data
- `parsed_metar_critical` - Parsed critical weather data
- `mock_llm_client` - Mocked LLM client
- `mock_metar_fetcher` - Mocked METAR fetcher
- Various state fixtures for workflow testing

## Mocking Strategy

### Mocking LLM Client

```python
from unittest.mock import MagicMock, patch
from app.core.llm_client import LLMResponse

mock_response = LLMResponse(
    content="天气分析结果...",
    model="ERNIE-4.0-8K",
    provider="qianfan"
)

mock_client = MagicMock()
mock_client.ainvoke = AsyncMock(return_value=mock_response)

with patch("app.core.llm_client.get_llm_client", return_value=mock_client):
    # Run tests
    pass
```

### Mocking METAR Fetcher

```python
from unittest.mock import patch

with patch("app.api.routes.fetch_metar_for_airport") as mock_fetch:
    mock_fetch.return_value = ("METAR...", {"icao": "ZSPD"})
    # Run tests
    pass
```

## Coverage Goals

- **Overall coverage**: ≥80%
- **Parse METAR node**: ≥90%
- **Risk assessor node**: ≥90%
- **Safety checker node**: ≥95%
- **API routes**: ≥85%

## Continuous Integration

Add to `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      - name: Run tests
        run: pytest --cov=app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Best Practices

1. **Use descriptive test names**: `test_parse_thunderstorm_with_gusty_wind`
2. **One assertion per test** (when practical)
3. **Test edge cases and boundary values**
4. **Mock external dependencies** (LLM, HTTP requests)
5. **Use fixtures for shared test data**
6. **Mark tests appropriately** (`@pytest.mark.asyncio`, `@pytest.mark.slow`)
7. **Keep tests independent** (no shared state between tests)
8. **Document complex test scenarios**

## Troubleshooting

### Import Errors

If you get import errors, ensure:
1. You're in the project root directory
2. The `app` module is in your Python path
3. Dependencies are installed

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

### Async Test Issues

If async tests fail, check:
1. `pytest-asyncio` is installed
2. Tests are marked with `@pytest.mark.asyncio`
3. `asyncio_mode = auto` in `pytest.ini`

### Coverage Issues

If coverage is low:
1. Check for uncovered branches in `htmlcov/index.html`
2. Add tests for error handling paths
3. Test edge cases and boundary conditions

## Contributing

When adding new features:
1. Write tests first (TDD approach)
2. Ensure all tests pass
3. Maintain coverage ≥80%
4. Update this README if needed

## License

Same as the main project license.
