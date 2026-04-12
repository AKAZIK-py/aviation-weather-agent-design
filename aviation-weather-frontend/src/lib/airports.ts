// 江浙沪机场数据 - 与后端 app/data/airports.py 保持一致

export interface Airport {
  icao: string;           // ICAO代码（如 ZSPD）
  iata: string;           // IATA代码（如 PVG）
  name_cn: string;        // 中文名称
  name_en: string;        // 英文名称
  city_cn: string;        // 所在城市（中文）
  city_en: string;        // 所在城市（英文）
  latitude: number;       // 纬度
  longitude: number;      // 经度
  elevation: number;      // 海拔（米）
  is_major: boolean;      // 是否为主要机场
}

// 江浙沪地区机场列表
export const AIRPORTS: Airport[] = [
  // ========== 上海市 ==========
  {
    icao: "ZSPD",
    iata: "PVG",
    name_cn: "上海浦东国际机场",
    name_en: "Shanghai Pudong International Airport",
    city_cn: "上海",
    city_en: "Shanghai",
    latitude: 31.1443,
    longitude: 121.8083,
    elevation: 4,
    is_major: true
  },
  {
    icao: "ZSSS",
    iata: "SHA",
    name_cn: "上海虹桥国际机场",
    name_en: "Shanghai Hongqiao International Airport",
    city_cn: "上海",
    city_en: "Shanghai",
    latitude: 31.1979,
    longitude: 121.3363,
    elevation: 3,
    is_major: true
  },
  
  // ========== 浙江省 ==========
  {
    icao: "ZSHC",
    iata: "HGH",
    name_cn: "杭州萧山国际机场",
    name_en: "Hangzhou Xiaoshan International Airport",
    city_cn: "杭州",
    city_en: "Hangzhou",
    latitude: 30.2295,
    longitude: 120.4344,
    elevation: 7,
    is_major: true
  },
  {
    icao: "ZSNB",
    iata: "NGB",
    name_cn: "宁波栎社国际机场",
    name_en: "Ningbo Lishe International Airport",
    city_cn: "宁波",
    city_en: "Ningbo",
    latitude: 29.8267,
    longitude: 121.4586,
    elevation: 4,
    is_major: false
  },
  {
    icao: "ZSWZ",
    iata: "WNZ",
    name_cn: "温州龙湾国际机场",
    name_en: "Wenzhou Longwan International Airport",
    city_cn: "温州",
    city_en: "Wenzhou",
    latitude: 27.9922,
    longitude: 120.6436,
    elevation: 4,
    is_major: false
  },
  
  // ========== 江苏省 ==========
  {
    icao: "ZSNJ",
    iata: "NKG",
    name_cn: "南京禄口国际机场",
    name_en: "Nanjing Lukou International Airport",
    city_cn: "南京",
    city_en: "Nanjing",
    latitude: 31.7420,
    longitude: 118.8622,
    elevation: 15,
    is_major: true
  },
  {
    icao: "ZSLY",
    iata: "LYG",
    name_cn: "连云港白塔埠机场",
    name_en: "Lianyungang Baitabu Airport",
    city_cn: "连云港",
    city_en: "Lianyungang",
    latitude: 34.5311,
    longitude: 119.1783,
    elevation: 5,
    is_major: false
  },
];

// 获取主要机场
export const getMajorAirports = (): Airport[] => {
  return AIRPORTS.filter(a => a.is_major);
};

// 按ICAO代码查找机场
export const getAirportByIcao = (icao: string): Airport | undefined => {
  return AIRPORTS.find(a => a.icao.toUpperCase() === icao.toUpperCase());
};

// 获取下拉框选项格式
export const getAirportOptions = (): Array<{ value: string; label: string; city: string }> => {
  return AIRPORTS
    .sort((a, b) => {
      // 主要机场优先，然后按城市排序
      if (a.is_major !== b.is_major) return b.is_major ? 1 : -1;
      return a.city_cn.localeCompare(b.city_cn, 'zh-CN');
    })
    .map(airport => ({
      value: airport.icao,
      label: `${airport.name_cn} (${airport.icao}/${airport.iata})`,
      city: airport.city_cn,
    }));
};

// 按城市分组
export const getAirportsGroupedByCity = (): Record<string, Airport[]> => {
  const grouped: Record<string, Airport[]> = {};
  for (const airport of AIRPORTS) {
    if (!grouped[airport.city_cn]) {
      grouped[airport.city_cn] = [];
    }
    grouped[airport.city_cn].push(airport);
  }
  return grouped;
};

// 按省份/地区分组
export const getAirportsGroupedByRegion = (): Record<string, Airport[]> => {
  const grouped: Record<string, Airport[]> = {
    "上海市": [],
    "浙江省": [],
    "江苏省": [],
  };

  for (const airport of AIRPORTS) {
    // 根据城市映射到省份
    if (airport.city_cn === "上海") {
      grouped["上海市"].push(airport);
    } else if (["杭州", "宁波", "温州"].includes(airport.city_cn)) {
      grouped["浙江省"].push(airport);
    } else if (["南京", "连云港"].includes(airport.city_cn)) {
      grouped["江苏省"].push(airport);
    }
  }

  return grouped;
};
