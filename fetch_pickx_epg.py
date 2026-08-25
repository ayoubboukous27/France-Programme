#!/usr/bin/env python3
"""
سحب ملف EPG (XMLTV) الجاهز لموقع pickx.be من بيانات iptv-org/api.

المصدر: guides.json المستضاف على GitHub Pages ضمن مشروع iptv-org/api.
هذا الملف يحتوي على قائمة الربط بين القنوات والمواقع المصدر، وكل مدخل
يحتوي حقل sources الذي يوفر روابط جاهزة (مولّدة مسبقاً) لملفات XMLTV
المستضافة تحت iptv-org/epg على GitHub Pages.

الاستخدام:
    python fetch_pickx_epg.py [--site pickx.be] [--out-dir ./epg]

في حال لم يوجد رابط جاهز في guides.json (الموقع معطل مؤقتاً أو غير مُدرج
كمصدر منشور)، يحاول السكربت تركيب الرابط المباشر المتوقع كخيار احتياطي.
"""

import argparse
import gzip
import io
import json
import sys
from pathlib import Path

import requests

GUIDES_URL = "https://iptv-org.github.io/api/guides.json"
FALLBACK_LANGS = ["nl", "fr"]  # pickx.be يبث بالهولندية والفرنسية (بلجيكا)


def fetch_guides():
    resp = requests.get(GUIDES_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_site_guide_urls(guides, site):
    urls = set()
    for entry in guides:
        if entry.get("site") != site:
            continue
        for source in entry.get("sources", []):
            url = source.get("url")
            if url:
                urls.add(url)
    return urls


def build_fallback_urls(site):
    urls = set()
    for lang in FALLBACK_LANGS:
        urls.add(f"https://iptv-org.github.io/epg/guides/{lang}/{site}.epg.xml")
        urls.add(f"https://iptv-org.github.io/epg/guides/{lang}/{site}.epg.xml.gz")
    return urls


def download_and_extract(url, timeout=60):
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    if url.endswith(".gz"):
        with gzip.GzipFile(fileobj=io.BytesIO(resp.content)) as f:
            return f.read().decode("utf-8")
    return resp.text


def main():
    parser = argparse.ArgumentParser(description="سحب EPG لموقع معيّن من iptv-org")
    parser.add_argument("--site", default="pickx.be", help="اسم الموقع كما في guides.json")
    parser.add_argument("--out-dir", default="epg", help="مجلد حفظ ملفات XML الناتجة")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] جلب guides.json ...")
    try:
        guides = fetch_guides()
        print(f"      تم جلب {len(guides)} مدخل.")
    except Exception as e:
        print(f"      تعذر جلب guides.json: {e}")
        guides = []

    print(f"[2/3] البحث عن مصادر EPG لموقع: {args.site}")
    urls = get_site_guide_urls(guides, args.site)

    if not urls:
        print("      لا يوجد رابط مسجّل في guides.json، تجربة روابط احتياطية معروفة ...")
        urls = build_fallback_urls(args.site)

    print(f"      عدد الروابط المرشحة: {len(urls)}")

    print(f"[3/3] تحميل وحفظ الملفات في: {out_dir}/")
    saved = 0
    for url in sorted(urls):
        try:
            print(f"  -> تحميل: {url}")
            xml_content = download_and_extract(url)
            file_name = url.split("/")[-1]
            if file_name.endswith(".gz"):
                file_name = file_name[:-3]
            out_path = out_dir / file_name
            out_path.write_text(xml_content, encoding="utf-8")
            print(f"     تم الحفظ: {out_path} ({len(xml_content):,} حرف)")
            saved += 1
        except requests.HTTPError as e:
            print(f"     تخطي (غير متوفر): {e}")
        except Exception as e:
            print(f"     خطأ غير متوقع: {e}")

    if saved == 0:
        print("لم يتم حفظ أي ملف EPG. تحقق من اسم الموقع أو حاول تشغيل سكرابر iptv-org/epg مباشرة.")
        sys.exit(1)

    print(f"تم! تم حفظ {saved} ملف/ملفات EPG بنجاح.")


if __name__ == "__main__":
    main()
