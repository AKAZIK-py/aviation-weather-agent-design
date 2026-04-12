// 航空气象智能分发系统 - JavaScript交互逻辑
// Aviation Weather Agent System - Frontend Logic

// ========================================
// 1. 气象规则数据库 (Layer1 & Layer2)
// ========================================

const weatherRulesDB = {
    wind: {
        thresholds: { low: 8, medium: 12, high: 17, critical: 17 },
        gustFactor: 1.5
    },
    visibility: {
        thresholds: { low: 10000, medium: 5000, high: 1500, critical: 1500 }
    },
    cloud: {
        thresholds: { low: 2000, medium: 1000, high: 500, critical: 500 },
        types: {
            CB: { description: "积雨云", severity: "high" },
            TCU: { description: "浓积云", severity: "medium" }
        }
    },
    weather: {
        phenomena: {
            TS: { description: "雷暴", severity: "critical", impact: "禁止起降" },
            TSRA: { description: "雷雨", severity: "critical", impact: "禁止起降" },
            SHRA: { description: "阵雨", severity: "medium", impact: "注意湿滑" },
            FG: { description: "雾", severity: "high", impact: "低能见度程序" },
            BR: { description: "轻雾", severity: "medium", impact: "能见度降低" },
            HZ: { description: "霾", severity: "low", impact: "能见度降低" },
            SN: { description: "雪", severity: "high", impact: "跑道污染" },
            FZRA: { description: "冻雨", severity: "critical", impact: "积冰风险" }
        }
    },
    riskLevels: {
        LOW: { level: "LOW", description: "气象条件良好，适航", action: "正常执行航班" },
        MEDIUM: { level: "MEDIUM", description: "气象条件一般，需注意", action: "加强监控，准备备选方案" },
        HIGH: { level: "HIGH", description: "气象条件较差，需谨慎", action: "评估风险，考虑延误或备降" },
        CRITICAL: { level: "CRITICAL", description: "气象条件恶劣，不满足安全标准", action: "暂停运行，等待条件改善" }
    }
};

// ========================================
// 2. METAR解析函数 (Layer1)
// ========================================

function parseMETAR(metarString) {
    const result = {
        raw: metarString,
        station: "",
        time: "",
        wind: { direction: null, speed: null, gust: null, unit: "MPS" },
        visibility: { value: null, unit: "M" },
        clouds: [],
        weather: [],
        temperature: null,
        dewpoint: null,
        qnh: null,
        trends: []
    };

    if (!metarString || metarString.trim() === "") {
        return result;
    }

    const tokens = metarString.trim().split(/\s+/);

    for (let i = 0; i < tokens.length; i++) {
        const token = tokens[i];

        if (/^[A-Z]{4}$/.test(token)) {
            result.station = token;
            continue;
        }

        if (/^\d{6}Z$/.test(token)) {
            result.time = token;
            continue;
        }

        const windMatch = token.match(/^(\d{3})(\d{2,3})(G(\d{2,3}))?(KT|MPS|KPH)?$/);
        if (windMatch) {
            result.wind.direction = parseInt(windMatch[1]);
            result.wind.speed = parseInt(windMatch[2]);
            if (windMatch[4]) result.wind.gust = parseInt(windMatch[4]);
            if (windMatch[5]) result.wind.unit = windMatch[5];
            continue;
        }

        const visMatch = token.match(/^(\d{4})(NDV)?|(CAVOK)|(9999)$/);
        if (visMatch) {
            if (visMatch[3] === "CAVOK" || visMatch[4] === "9999") {
                result.visibility.value = 10000;
            } else if (visMatch[1]) {
                result.visibility.value = parseInt(visMatch[1]);
            }
            continue;
        }

        const cloudMatch = token.match(/^(FEW|SCT|BKN|OVC)(\d{3})(CB|TCU)?$/);
        if (cloudMatch) {
            result.clouds.push({
                coverage: cloudMatch[1],
                height: parseInt(cloudMatch[2]) * 100,
                type: cloudMatch[3] || null
            });
            continue;
        }

        const wxMatch = token.match(/^(TS|TSRA|SHRA|FG|BR|HZ|SN|FZRA|GR|VA|RA|DZ)(VC)?(MI|BC|PR|DR|BL|SH|TS|FZ)?$/);
        if (wxMatch) {
            result.weather.push({ code: wxMatch[1], intensity: wxMatch[3] || "moderate" });
            continue;
        }

        const tempMatch = token.match(/^(-?\d{1,2})\/(-?\d{1,2})$/);
        if (tempMatch) {
            result.temperature = parseInt(tempMatch[1]);
            result.dewpoint = parseInt(tempMatch[2]);
            continue;
        }

        const qnhMatch = token.match(/^[QA](\d{4})$/);
        if (qnhMatch) {
            result.qnh = parseInt(qnhMatch[1]);
            continue;
        }

        if (/^(NOSIG|BECMG|TEMPO)/.test(token)) {
            result.trends.push(token);
        }
    }

    return result;
}

// ========================================
// 3. 风险评估函数 (Layer2)
// ========================================

function assessRisk(parsedMETAR) {
    const risk = { level: "LOW", score: 0, warnings: [] };

    if (!parsedMETAR || !parsedMETAR.wind) return risk;

    const windSpeed = parsedMETAR.wind.speed || 0;
    const gustSpeed = parsedMETAR.wind.gust || 0;

    // 风速评估
    if (windSpeed > 17) {
        risk.score += 40;
        risk.warnings.push("风速超标: " + windSpeed + " m/s");
    } else if (windSpeed > 12) {
        risk.score += 30;
        risk.warnings.push("风速较高: " + windSpeed + " m/s");
    } else if (windSpeed > 8) {
        risk.score += 15;
        risk.warnings.push("风速中等: " + windSpeed + " m/s");
    }

    // 阵风评估
    if (gustSpeed > 0) {
        const gustDelta = gustSpeed - windSpeed;
        if (gustDelta > 10) {
            risk.score += 20;
            risk.warnings.push("阵风强烈: " + gustSpeed + " m/s");
        } else if (gustDelta > 5) {
            risk.score += 10;
            risk.warnings.push("阵风: " + gustSpeed + " m/s");
        }
    }

    // 能见度评估
    const visibility = parsedMETAR.visibility.value || 10000;
    if (visibility < 1500) {
        risk.score += 40;
        risk.warnings.push("能见度严重不足: " + visibility + "m");
    } else if (visibility < 5000) {
        risk.score += 30;
        risk.warnings.push("能见度较低: " + visibility + "m");
    } else if (visibility < 10000) {
        risk.score += 15;
        risk.warnings.push("能见度中等: " + visibility + "m");
    }

    // 云况评估
    if (parsedMETAR.clouds && parsedMETAR.clouds.length > 0) {
        parsedMETAR.clouds.forEach(cloud => {
            if (cloud.type === "CB") {
                risk.score += 30;
                risk.warnings.push("积雨云 (CB) at " + cloud.height + "ft");
            } else if (cloud.type === "TCU") {
                risk.score += 20;
                risk.warnings.push("浓积云 (TCU) at " + cloud.height + "ft");
            }
            if (cloud.height < 500) {
                risk.score += 20;
                risk.warnings.push("云底高过低: " + cloud.height + "ft");
            }
        });
    }

    // 天气现象评估
    if (parsedMETAR.weather && parsedMETAR.weather.length > 0) {
        parsedMETAR.weather.forEach(wx => {
            const phenomenon = weatherRulesDB.weather.phenomena[wx.code];
            if (phenomenon) {
                if (phenomenon.severity === "critical") {
                    risk.score += 50;
                    risk.warnings.push(phenomenon.description + " (" + wx.code + ") - " + phenomenon.impact);
                } else if (phenomenon.severity === "high") {
                    risk.score += 30;
                    risk.warnings.push(phenomenon.description + " (" + wx.code + ")");
                } else if (phenomenon.severity === "medium") {
                    risk.score += 15;
                    risk.warnings.push(phenomenon.description + " (" + wx.code + ")");
                }
            }
        });
    }

    // 判定最终风险等级
    if (risk.score >= 100) {
        risk.level = "CRITICAL";
    } else if (risk.score >= 60) {
        risk.level = "HIGH";
    } else if (risk.score >= 30) {
        risk.level = "MEDIUM";
    }

    return risk;
}

// ========================================
// 4. 角色解释生成函数 (Layer3)
// ========================================

function generateRoleExplanation(role, parsedMETAR, riskAssessment) {
    const riskLevel = riskAssessment.level;
    const windSpeed = parsedMETAR.wind ? (parsedMETAR.wind.speed || 0) : 0;
    const visibility = parsedMETAR.visibility ? (parsedMETAR.visibility.value || 10000) : 10000;
    
    let explanation = "";
    
    if (role === "dispatcher") {
        if (riskLevel === "CRITICAL") {
            explanation = "【签派决策建议】当前气象条件不满足安全运行标准。\n";
            explanation += "风速" + windSpeed + "m/s，能见度" + visibility + "m，存在严重天气现象。\n";
            explanation += "建议：暂停航班运行，等待条件改善。考虑备降或延误。";
        } else if (riskLevel === "HIGH") {
            explanation = "【签派决策建议】气象条件较差，需谨慎评估。\n";
            explanation += "风速" + windSpeed + "m/s，能见度" + visibility + "m。\n";
            explanation += "建议：评估风险，准备备选方案，加强监控。";
        } else if (riskLevel === "MEDIUM") {
            explanation = "【签派决策建议】气象条件一般，需注意变化。\n";
            explanation += "风速" + windSpeed + "m/s，能见度" + visibility + "m。\n";
            explanation += "建议：正常执行，但需监控天气演变。";
        } else {
            explanation = "【签派决策建议】气象条件良好，适航。\n";
            explanation += "风速" + windSpeed + "m/s，能见度" + visibility + "m。\n";
            explanation += "建议：正常执行航班。";
        }
    } else if (role === "ground") {
        if (riskLevel === "CRITICAL" || riskLevel === "HIGH") {
            explanation = "【地面保障提示】当前天气影响地面作业安全。\n";
            explanation += "建议：减少或暂停户外作业，注意人员安全。";
        } else {
            explanation = "【地面保障提示】天气条件允许正常作业。\n";
            explanation += "建议：按标准流程执行。";
        }
    } else if (role === "controller") {
        if (riskLevel === "CRITICAL" || riskLevel === "HIGH") {
            explanation = "【管制提示】当前天气影响空域运行。\n";
            explanation += "建议：调整间隔标准，注意复飞预案。";
        } else {
            explanation = "【管制提示】天气条件正常。\n";
            explanation += "建议：按标准程序执行。";
        }
    } else if (role === "meteorologist") {
        explanation = "【天气形势分析】\n";
        if (parsedMETAR.weather && parsedMETAR.weather.length > 0) {
            explanation += "当前天气现象：" + parsedMETAR.weather.map(function(w) { return w.code; }).join(", ") + "\n";
        }
        if (parsedMETAR.clouds && parsedMETAR.clouds.length > 0) {
            explanation += "云况：" + parsedMETAR.clouds.map(function(c) { return c.coverage + String(c.height/100); }).join(", ") + "\n";
        }
        explanation += "风险评分：" + riskAssessment.score + "分";
    }
    
    return explanation;
}

// ========================================
// 5. UI更新函数
// ========================================

function updateParseResult(parsed) {
    var windValue = document.getElementById('wind-value');
    if (windValue) {
        if (parsed.wind && parsed.wind.speed !== null) {
            var gustText = parsed.wind.gust ? " G" + parsed.wind.gust : "";
            windValue.textContent = parsed.wind.direction + "° / " + parsed.wind.speed + gustText + " " + parsed.wind.unit;
        } else {
            windValue.textContent = 'N/A';
        }
    }
    
    var visValue = document.getElementById('visibility-value');
    if (visValue) {
        if (parsed.visibility && parsed.visibility.value !== null) {
            var visKm = parsed.visibility.value >= 1000 
                ? (parsed.visibility.value / 1000) + " km" 
                : parsed.visibility.value + " m";
            visValue.textContent = visKm;
        } else {
            visValue.textContent = 'N/A';
        }
    }
    
    var cloudValue = document.getElementById('cloud-value');
    if (cloudValue) {
        if (parsed.clouds && parsed.clouds.length > 0) {
            var cloudText = parsed.clouds.map(function(c) {
                var type = c.type ? " " + c.type : "";
                return c.coverage + (c.height / 100) + type;
            }).join(" | ");
            cloudValue.textContent = cloudText;
        } else {
            cloudValue.textContent = "无显著云";
        }
    }
}

function updateRiskDisplay(risk) {
    var riskLevelEl = document.getElementById('risk-level');
    if (riskLevelEl) {
        riskLevelEl.textContent = risk.level;
        riskLevelEl.className = "risk-badge " + risk.level.toLowerCase();
    }
    
    var riskSummary = document.getElementById('risk-summary');
    if (riskSummary) {
        var ruleConfig = weatherRulesDB.riskLevels[risk.level];
        riskSummary.innerHTML = "<p><strong>" + ruleConfig.description + "</strong></p>" +
            "<p>建议操作：" + ruleConfig.action + "</p>" +
            "<p>风险评分：" + risk.score + "分</p>";
    }
    
    var warningBadges = document.getElementById('warning-badges');
    if (warningBadges) {
        warningBadges.innerHTML = "";
        if (risk.warnings && risk.warnings.length > 0) {
            risk.warnings.forEach(function(warning) {
                var badge = document.createElement("span");
                badge.className = "warning-badge";
                badge.textContent = warning;
                warningBadges.appendChild(badge);
            });
        }
    }
}

function updateExplanation(explanation) {
    var outputEl = document.getElementById('explanation-output');
    if (outputEl) {
        outputEl.textContent = explanation;
        outputEl.style.display = "block";
    }
}

// ========================================
// 6. 主分析函数
// ========================================

function analyzeWeather() {
    var metarInput = document.getElementById('metar-input');
    
    if (!metarInput) {
        console.error("找不到METAR输入框");
        return;
    }
    
    var metar = metarInput.value.trim();
    
    if (!metar) {
        alert("请输入METAR报文");
        return;
    }
    
    // Layer 1: 解析METAR
    var parsed = parseMETAR(metar);
    updateParseResult(parsed);
    
    // Layer 2: 风险评估
    var risk = assessRisk(parsed);
    updateRiskDisplay(risk);
    
    // Layer 3: 获取角色解释
    var roleSelector = document.querySelector('input[name="role"]:checked');
    var selectedRole = roleSelector ? roleSelector.value : "dispatcher";
    
    var explanation = generateRoleExplanation(selectedRole, parsed, risk);
    updateExplanation(explanation);
    
    console.log("分析完成", { parsed: parsed, risk: risk, selectedRole: selectedRole });
}

// ========================================
// 7. 事件监听器初始化
// ========================================

document.addEventListener("DOMContentLoaded", function() {
    console.log("航空气象智能分发系统初始化...");
    
    // 绑定分析按钮
    var analyzeBtn = document.getElementById('analyze-btn');
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', analyzeWeather);
    } else {
        console.error("找不到分析按钮");
    }
    
    // 绑定角色切换
    var roleRadios = document.querySelectorAll('input[name="role"]');
    roleRadios.forEach(function(radio) {
        radio.addEventListener('change', function() {
            var metarInput = document.getElementById('metar-input');
            if (metarInput && metarInput.value.trim()) {
                analyzeWeather();
            }
        });
    });
    
    // 绑定清空按钮
    var clearBtn = document.getElementById('clear-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', function() {
            document.getElementById('metar-input').value = "";
            document.getElementById('taf-input').value = "";
            document.getElementById('explanation-output').textContent = "";
            document.getElementById('explanation-output').style.display = "none";
            document.getElementById('wind-value').textContent = "N/A";
            document.getElementById('visibility-value').textContent = "N/A";
            document.getElementById('cloud-value').textContent = "N/A";
            document.getElementById('risk-level').textContent = "LOW";
            document.getElementById('risk-summary').innerHTML = "";
            document.getElementById('warning-badges').innerHTML = "";
        });
    }
    
    // 加载示例数据
    var loadExampleBtn = document.getElementById('load-example');
    if (loadExampleBtn) {
        loadExampleBtn.addEventListener('click', function() {
            document.getElementById('metar-input').value = "ZBAA 110800Z 18015G25KT 3000 TSRA BKN010CB 25/22 Q1008 TEMPO 2500";
            document.getElementById('taf-input').value = "TAF ZBAA 110500Z 1106/1118 18012KT 6000 SCT030 TEMPO 1108/1112 3000 TSRA BKN010CB";
        });
    }
    
    console.log("初始化完成");
});