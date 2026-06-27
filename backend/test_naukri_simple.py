import requests

# ------------ paste fresh values from your browser here ----------------------------
COOKIE = '_t_ds=3d5fcfe1782505859-443d5fcfe-03d5fcfe; J=0; ak_bmsc=E00075AE00C21CCD24A2B656D87A1C5E~000000000000000000000000000000~YAAQ6dxVuLn6NgSfAQAA6eugBQCbOEFDVPQ/iNK1DSWDwHvkqpyfNRdqN5in5WbIZmnU756y00FJwaeCftSh6mG7djgMQgZnzmofH51VEc8wpbrCX0JBQpEpaduS/eZyGk3KByS7b1RrJBZFVFptQvRDyqCorLbtj9aWre/U86P+Lxcs7LGexPOcmuko14mRzohZKCOjt430HNizu4o8+3TezNWoGzIvUkCOO+H36pCYB4/bYdOHRdsmfczO9VFydcQCq2E8vwzT56QyhPjnjqGajgpEPhOtQbD1L5Vw4r4HuDexfBtmLNr6m4F361IkaSoxUp48ZBOzFPVeUKcRuhnOHsNtcmA4WY2FAezers4aVlgMP+YpcDm2SARcywTtivrH5xywvG4ukMPS9ZiSp5UlxUd6GiVkPM1610UrwiuJboXD9lXnfAFWU3ANbrUM3vqOkKrzzU3tO3YO3z1o09hYSGwhdz3lhHeXoC1jN/CUAoEknJpdfUA=; _gcl_au=1.1.956321427.1782505860; _gcl_aw=GCL.1782505860.EAIaIQobChMIrabO4d-llQMVP6ZmAh1dvRtrEAAYASAAEgLJN_D_BwE; _gcl_dc=GCL.1782505860.EAIaIQobChMIrabO4d-llQMVP6ZmAh1dvRtrEAAYASAAEgLJN_D_BwE; _gcl_gs=2.1.k1$i1782505858$u155968292; _ga=GA1.1.1980197997.1782505860; test=naukri.com; _t_us=6A3EE189; _t_s=seo; _t_sd=google; _t_r=1030%2F%2F; persona=default; __gads=ID=1f1195a39bfaae77:T=1782505904:RT=1782505904:S=ALNI_MaotO69Tmic04hAsNwJcN-pDO1y_g; __gpi=UID=000014896af13b3e:T=1782505904:RT=1782505904:S=ALNI_MZz-cDDk_HTyHzqxjkrvYpgLBCbtQ; __eoi=ID=7b3020a20ed80a19:T=1782505904:RT=1782505904:S=AA-Afjapovh7uvLwg877NzxgRwb1; g_state={"i_l":0,"i_ll":1782505904913,"i_b":"BVXK2dtJedMfLqSHn6Xtu9zOEFhQSmGSEUgpuYHZqHs","i_e":{"enable_itp_optimization":24},"i_et":1782505904913}; bm_sv=027D4361F26C6DE3DA77D736C0DC71F4~YAAQ6dxVuKATNwSfAQAA1g6mBQDFhgo08PIOdU+XZVfPmVH7v6LTpJqEUq7qv+3rhXpfScseRFjYLhcy8EzUAxcbY4gC6aCbdg8BAmdu1xC6PVnvd9FFC+Fct44+QTr95ZYpL+Jx5lNj1VsxEFVkgdRQuBiGN5t1V8lbd9TLmCWrh+uWMqLR4L9X7hWDeZ4JQ8nWcf9g3Ttk1nYrd1XoMwJw4AtNG+VfwLkygbcHRLpS5dVxyeV/EcDAydYsv3xTQg==~1; HOWTORT=ul=1782506196220&r=https%3A%2F%2Fwww.naukri.com%2Fqa-automation-qa-engineer-qa-process-manual-testing-jobs-in-gurugram%3Fk%3Dqa%2520automation%252C%2520qa%2520engineer%252C%2520qa%2520process%252C%2520manual%2520testing%26l%3Dgurugram%26experience%3D3&hd=1782506196565; _ga_K2YBNZVRLL=GS2.1.s1782505860$o1$g1$t1782506196$j60$l0$h0'
NKPARAM = "bf4UNxrqZLusTZSMa+kI38a8H1aV5RoW7qzS5+PpHoQUQhtHWRulOOMe2XIL+b4vOmr8fh7M7g0CC01TQKAk1w=="
# -----------------------------------------------------------------------------------

URL = (
    "https://www.naukri.com/jobapi/v3/search"
    "?noOfResults=20&urlType=search_by_key_loc&searchType=adv"
    "&location=gurugram"
    "&keyword=qa%20automation%2C%20qa%20engineer%2C%20qa%20process%2C%20manual%20testing"
    "&pageNo=1&experience=3"
    "&k=qa%20automation%2C%20qa%20engineer%2C%20qa%20process%2C%20manual%20testing"
    "&l=gurugram&experience=3"
    "&seoKey=qa-automation-qa-engineer-qa-process-manual-testing-jobs-in-gurugram"
    "&src=jobsearchDesk&latLong="
)

HEADERS = {
    "accept": "application/json",
    "accept-language": "en-GB,en;q=0.9",
    "appid": "109",
    "clientid": "d3skt0p",
    "content-type": "application/json",
    "cookie": COOKIE,
    "gid": "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
    "nkparam": NKPARAM,
    "priority": "u=1, i",
    "referer": (
        "https://www.naukri.com/"
        "qa-automation-qa-engineer-qa-process-manual-testing-jobs-in-gurugram"
        "?k=qa%20automation%2C%20qa%20engineer%2C%20qa%20process%2C%20manual%20testing"
        "&l=gurugram&experience=3"
    ),
    "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "systemid": "Naukri",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
}

resp = requests.get(URL, headers=HEADERS, timeout=30)
print("Status:", resp.status_code)

if resp.status_code == 200:
    data = resp.json()
    print(data)
    jobs = data.get("jobDetails", [])
    print(f"Jobs found: {len(jobs)}")
    for j in jobs:
        print(f"  - {j.get('title')} @ {j.get('companyName')}")
else:
    print("Body:", resp.text[:500])
