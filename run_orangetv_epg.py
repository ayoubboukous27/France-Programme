#!/usr/bin/env python3
"""
سكربت Python يشغّل أوامر iptv-org/epg الخاصة بموقع orangetv.orange.es:

  1. npm run grab -- --sites=orangetv.orange.es
     يولّد ملف EPG (guide.xml) عبر زيارة الموقع فعليًا واستخراج البرامج.

  2. npm run channels:parse -- \
         --config=./sites/orangetv.orange.es/orangetv.orange.es.config.js \
         --output=./sites/orangetv.orange.es/orangetv.orange.es.channels.xml
     يولّد/يحدّث ملف قائمة القنوات (channels.xml) لهذا الموقع.

المتطلبات:
  - Node.js وnpm مثبّتان.
  - مستودع iptv-org/epg مستنسخ (هذا السكربت يستنسخه تلقائيًا إن لم يوجد).

الاستخدام:
    python run_orangetv_epg.py [--repo-dir ./epg-src] [--skip-clone]
                                [--skip-install] [--output-dir ./output]
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/iptv-org/epg.git"
SITE = "orangetv.orange.es"


def run(cmd, cwd=None):
    print(f"\n$ {' '.join(cmd)}  (cwd={cwd or '.'})")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"فشل الأمر برمز خروج {result.returncode}")
        sys.exit(result.returncode)


def ensure_repo(repo_dir: Path, skip_clone: bool):
    if repo_dir.exists():
        print(f"المستودع موجود مسبقًا في: {repo_dir}")
        return
    if skip_clone:
        print(f"لم يتم العثور على {repo_dir} و --skip-clone مفعّل. توقف.")
        sys.exit(1)
    print(f"استنساخ iptv-org/epg إلى: {repo_dir} ...")
    run(["git", "clone", "--depth", "1", "-b", "master", REPO_URL, str(repo_dir)])


def check_node():
    for tool in ("node", "npm"):
        if shutil.which(tool) is None:
            print(f"الأداة '{tool}' غير مثبّتة أو غير موجودة في PATH.")
            print("ثبّت Node.js (يتضمن npm) من https://nodejs.org ثم أعد المحاولة.")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=f"توليد EPG وقائمة قنوات لموقع {SITE}")
    parser.add_argument("--repo-dir", default="epg-src", help="مسار مستودع iptv-org/epg")
    parser.add_argument("--skip-clone", action="store_true", help="لا تستنسخ المستودع، افترض أنه موجود")
    parser.add_argument("--skip-install", action="store_true", help="تخطي npm install (إن كانت node_modules موجودة)")
    parser.add_argument("--output-dir", default="output", help="مجلد نسخ الملفات الناتجة إليه")
    args = parser.parse_args()

    check_node()

    repo_dir = Path(args.repo_dir).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    ensure_repo(repo_dir, args.skip_clone)

    if not args.skip_install:
        print("\nتثبيت اعتماديات npm ...")
        run(["npm", "install"], cwd=str(repo_dir))

    print(f"\n[1/2] توليد EPG لموقع {SITE} (npm run grab) ...")
    run(["npm", "run", "grab", "--", f"--sites={SITE}"], cwd=str(repo_dir))

    config_path = f"./sites/{SITE}/{SITE}.config.js"
    channels_output = f"./sites/{SITE}/{SITE}.channels.xml"

    print(f"\n[2/2] توليد/تحديث قائمة القنوات (npm run channels:parse) ...")
    run(
        ["npm", "run", "channels:parse", "--", f"--config={config_path}", f"--output={channels_output}"],
        cwd=str(repo_dir),
    )

    guide_src = repo_dir / "guide.xml"
    channels_src = repo_dir / "sites" / SITE / f"{SITE}.channels.xml"

    copied = []
    if guide_src.exists():
        dest = out_dir / f"{SITE}.epg.xml"
        shutil.copy2(guide_src, dest)
        copied.append(dest)
    else:
        print(f"تحذير: لم يتم العثور على {guide_src} بعد التوليد.")

    if channels_src.exists():
        dest = out_dir / f"{SITE}.channels.xml"
        shutil.copy2(channels_src, dest)
        copied.append(dest)
    else:
        print(f"تحذير: لم يتم العثور على {channels_src} بعد التوليد.")

    if not copied:
        print("\nلم يتم نسخ أي ملف ناتج. راجع الأخطاء أعلاه.")
        sys.exit(1)

    print("\nتم بنجاح! الملفات الناتجة:")
    for p in copied:
        size = p.stat().st_size
        print(f"  - {p} ({size:,} بايت)")


if __name__ == "__main__":
    main()
