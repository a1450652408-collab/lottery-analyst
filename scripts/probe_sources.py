# -*- coding: utf-8 -*-
"""临时诊断：从 GitHub Actions（境外 Azure）探测各彩票数据源可达性。
运行完即可删除；结果直接打印到 Actions 日志。"""
import urllib.request, urllib.error, time, re, ssl

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

TARGETS = [
    ("huiniao-kl8", "http://api.huiniao.top/interface/home/lotteryHistory?type=klb&page=1&limit=3"),
    ("cwl-kl8", "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=kl8&issueCount=3"),
    ("sporttery-dlt", "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?gameNo=85&provinceId=0&pageSize=3&isVerify=1&pageNo=1"),
    ("zhcw-kl8", "https://www.zhcw.com/kjxx/kl8/"),
    ("500-kl8", "https://datachart.500.com/kl8/history/newinc/history.php?limit=5"),
    ("163-kl8", "https://caipiao.163.com/award/kl8/"),
    ("vvhan", "https://api.vvhan.com/api/lottery?type=kl8"),
    ("pearktrue", "https://api.pearktrue.cn/api/lottery/?type=kl8"),
    ("52vmy", "https://api.52vmy.cn/api/query/lottery?type=kl8"),
    ("raw-github", "https://raw.githubusercontent.com/a1450652408-collab/lottery-analyst/master/README.md"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def hit(name, url):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Referer": "https://www.cwl.gov.cn/ygkj/wqkjgg/kl8/",
            "Accept": "application/json, text/html, */*",
        })
        with urllib.request.urlopen(req, timeout=18, context=ctx) as r:
            body = r.read(200000)
            dt = time.time() - t0
            txt = body.decode("utf-8", "ignore")
            per = re.findall(r"20\d{5}", txt)[:3]
            day = re.findall(r"20\d{2}-\d{2}-\d{2}", txt)[:3]
            print(f"  [{name}] {r.status} {len(body)}B {dt:.1f}s | 期号样本={per} 日期样本={day}")
    except urllib.error.HTTPError as e:
        print(f"  [{name}] HTTP {e.code} {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"  [{name}] FAIL {type(e).__name__}: {str(e)[:70]} {time.time()-t0:.1f}s")


def run():
    print("=== 数据源可达性探测（境外 IP 视角）===")
    for name, url in TARGETS:
        hit(name, url)
    print("=== 探测结束 ===")
