import datetime
import json
import os
import random
import time
import urllib.error
import urllib.request


class CloudTaiwanMarketEngine:

    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]
        self.base_dir = os.path.dirname(__file__)

    def _get_db_path(self, year_str):
        return os.path.join(self.base_dir, f"data/history_{year_str}.json")

    def _load_db(self, year_str):
        path = self._get_db_path(year_str)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_db(self, year_str, data):
        path = self._get_db_path(year_str)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _safe_request(self, url):
        retries = 3
        for attempt in range(retries):
            try:
                # 每次連線隨機延遲 5-10 秒防止被證交所阻斷
                time.sleep(random.uniform(5.0, 10.0))
                headers = {"User-Agent": random.choice(self.user_agents)}
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=25) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                print(f"[!] 連線失敗，第 {attempt+1} 次重試... 錯誤: {e}")
                time.sleep(10)
        return None

    def execute(self):
        # 取得今天日期（台灣時間）
        today = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        
        # 週末不執行
        if today.weekday() >= 5:
            print("[INFO] 週末台股不開盤，結束任務。")
            return

        date_str = today.strftime("%Y%m%d")
        year_str = date_str[:4]
        formatted_date = today.strftime("%Y-%m-%d")
        
        database = self._load_db(year_str)
        has_new_data = False

        print(f"[*] 開始抓取上市個股數據 ({formatted_date})...")
        twse_url = f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&date={date_str}&type=ALL"
        twse_data = self._safe_request(twse_url)

        if twse_data and "data9" in twse_data:
            for row in twse_data["data9"]:
                stock_id = row[0].strip()
                if len(stock_id) != 4 or not stock_id.isdigit():
                    continue
                
                if stock_id not in database:
                    database[stock_id] = []
                if any(day["date"] == formatted_date for day in database[stock_id]):
                    continue
                
                try:
                    database[stock_id].append({
                        "date": formatted_date,
                        "market": "TWSE",
                        "open": float(row[5].replace(",", "")),
                        "high": float(row[6].replace(",", "")),
                        "low": float(row[7].replace(",", "")),
                        "close": float(row[8].replace(",", "")),
                        "volume": int(int(row[2].replace(",", "")) / 1000),
                        "foreign_buy": 0, "trust_buy": 0, "major_players_buy": 0
                    })
                    has_new_data = True
                except ValueError:
                    continue

        print(f"[*] 開始抓取上櫃個股數據 ({formatted_date})...")
        roc_year = str(int(year_str) - 1912)
        tpex_date_str = f"{roc_year}/{date_str[4:6]}/{date_str[6:]}"
        tpex_url = f"https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&d={tpex_date_str}&se=EW&_={int(time.time()*1000)}"
        
        tpex_data = self._safe_request(tpex_url)
        if tpex_data and "aaData" in tpex_data:
            for row in tpex_data["aaData"]:
                stock_id = row[0].strip()
                if len(stock_id) != 4 or not stock_id.isdigit():
                    continue
                if stock_id not in database:
                    database[stock_id] = []
                if any(day["date"] == formatted_date for day in database[stock_id]):
                    continue
                    
                try:
                    database[stock_id].append({
                        "date": formatted_date,
                        "market": "TPEX",
                        "open": float(row[4].replace(",", "")),
                        "high": float(row[5].replace(",", "")),
                        "low": float(row[6].replace(",", "")),
                        "close": float(row[7].replace(",", "")),
                        "volume": int(int(row[8].replace(",", "")) / 1000),
                        "foreign_buy": 0, "trust_buy": 0, "major_players_buy": 0
                    })
                    has_new_data = True
                except ValueError:
                    continue

        if has_new_data:
            print("[*] 抓取三大法人籌碼...")
            chips_url = f"https://www.twse.com.tw/fund/T86?response=json&date={date_str}&selectType=ALL"
            chips_data = self._safe_request(chips_url)
            if chips_data and "data" in chips_data:
                for row in chips_data["data"]:
                    sid = row[0].strip()
                    if sid in database:
                        try:
                            f_buy = int(int(row[7].replace(",", "")) / 1000)
                            t_buy = int(int(row[10].replace(",", "")) / 1000)
                            d_buy = int(int(row[11].replace(",", "")) / 1000)
                            for day in database[sid]:
                                if day["date"] == formatted_date:
                                    day["foreign_buy"] = f_buy
                                    day["trust_buy"] = t_buy
                                    day["major_players_buy"] = f_buy + t_buy + d_buy
                                    break
                        except ValueError:
                            continue

            self._save_db(year_str, database)
            print(f"[✓] 歷史資料庫同步完成！")
        else:
            print("[#] 今日無新數據（非交易日或伺服器尚未更新）。")


if __name__ == "__main__":
    engine = CloudTaiwanMarketEngine()
    engine.execute()
