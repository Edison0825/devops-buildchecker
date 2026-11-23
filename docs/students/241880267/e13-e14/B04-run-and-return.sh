#!/usr/bin/env bash
# 在 B04 自己的隔离 Linux 仓库根目录运行；包、同名 .sha256 位于参数指定的位置。
set -euo pipefail
umask 077
pkg=$(realpath "${1:?用法：bash B04-run-and-return.sh /路径/A04-to-B04-SDS-01.tar.gz}")
name=A04-to-B04-SDS-01
[[ $(basename "$pkg") == "$name.tar.gz" ]]
(cd "$(dirname "$pkg")" && sha256sum -c "$name.tar.gz.sha256")
for f in run_e11e12.py labs/e13e14/{handoff_a_to_b,scan_runtime_logs}.py labs/e11e12/pipeline.py; do test -f "$f" || {
    echo "缺少 $f，请先完成 B 侧环境准备"
    exit 1
}; done
grep -q fixed_report_sha256 labs/e11e12/pipeline.py || {
    echo '此版本未校验 fixed_report_sha256，停止'
    exit 1
}
sid=$(git config --local --get user.name)
[[ $sid =~ ^[0-9]{6,16}$ ]] || {
    echo '请在个人隔离仓库配置 B 侧执行者学号'
    exit 1
}
image=$(docker image inspect "course-e11e12:$sid" --format '{{.Id}}')
mkdir -p work data
out=$(mktemp -d work/B04-SDS-receipt-XXXXXXXX)
d=$(mktemp -d data/B04-SDS-input-XXXXXXXX)
printf '本次目录：%s %s\n' "$out" "$d"
printf 'executor=%s\ncommit=%s\nimage=%s\n' "$sid" "$(git rev-parse HEAD)" "$image" >"$out/environment.txt"
git status --short --untracked-files=no >>"$out/environment.txt"
python3 - "$pkg" "$d" <<'PY'
import sys, tarfile
from pathlib import Path
root = Path(sys.argv[2]).resolve()
with tarfile.open(sys.argv[1]) as t:
    for m in t.getmembers():
        if not ((m.isfile() or m.isdir()) and (root/m.name).resolve().is_relative_to(root)):
            raise SystemExit('交接包含非普通文件或异常路径')
    t.extractall(root)
PY
p="$d/$name"
base=f103947b89737ef40c5920a44cfc1df7911b6dfe
target=3d658f2049015bba04df8d425d378fd196b15702
git clone -q -b a04-sds "$p/sds.bundle" "$d/repo"
test "$(git -C "$d/repo" rev-parse HEAD)" = "$target"
git -C "$d/repo" merge-base --is-ancestor "$base" "$target"
python3 labs/e13e14/handoff_a_to_b.py --a-result "$p/a-result/result.json" --target-sha "$target" --out "$d/fixed-md.json"
cmp "$p/fixed-md.json" "$d/fixed-md.json"
cp "$d/fixed-md.json" "$out/handoff.json"
python3 - "$d" "$p" "$out" "$base" "$target" <<'PY'
import hashlib, json, sys
from pathlib import Path
d, p, out = map(Path, sys.argv[1:4]); r=json.loads((p/'a-result/request.json').read_text())
assert (r['mode'],r['base'],r['target']) == ('e11-a',*sys.argv[4:])
r.update(mode='e11-b', repo=f'/course/{d}/repo', candidate=f'/course/{p}/real-candidate.Dockerfile', fixed_report=f'/course/{d}/fixed-md.json', fixed_report_sha256=hashlib.sha256((d/'fixed-md.json').read_bytes()).hexdigest())
(out/'request.json').write_text(json.dumps(r,indent=2)+'\n')
PY
rc=0
python3 run_e11e12.py run --request "$out/request.json" --out "$out/run" >"$out/console.log" 2>&1 || rc=$?
printf '%s\n' "$rc" >"$out/exit-code.txt"
# 只复制当前运行的验收文件。完整构建目录保留在 B04，不传项目快照或 .git。
mkdir "$out/return"
cp "$out"/{request.json,handoff.json,environment.txt,console.log,exit-code.txt} "$out/return/"
for f in result.json draft-build/result.json fixed-md-input.json fixed-md.json repair.json candidate.patch validation/validation.json recheck.json; do
    if test -f "$out/run/$f"; then
        mkdir -p "$out/return/$(dirname "$f")"
        cp "$out/run/$f" "$out/return/$f"
    fi
done
verdict=0
python3 - "$out/return" <<'PY' >"$out/return/summary.txt" 2>&1 || verdict=$?
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]); get=lambda f:json.loads((p/f).read_text()); sha=lambda f:hashlib.sha256((p/f).read_bytes()).hexdigest()
r=get('result.json'); q=get('request.json'); h=get('handoff.json'); stages=[s['name'] for s in r['stages']]
print('B job/trace:',r['job_id'],r['trace_id'],'status:',r['status'],'error:',r.get('error')); print('stages:',stages)
assert (p/'exit-code.txt').read_text().strip()=='0' and r['status']=='SUCCEEDED'
assert stages==['draft','fixed-md','repair','recheck'] and (r['base_commit'],r['target_commit'])==(q['base'],q['target'])
s=h['source_report']; print('A source:',s)
assert (s['job_id'],s['trace_id'],s['sha256'])==('job-2f74a415c3f74acabfadacb90c2fda8b','trace-21016570683c4f0fa2750b7dc1c6a6e4','1e903bebbc364fe9995261b5da0abcbd8959f23ef7526a53a1af25a91a5166de')
assert q['fixed_report_sha256']==sha('handoff.json') and get('fixed-md-input.json')==h
assert get('repair.json')['data']['input_report']['sha256']==sha('fixed-md.json')
e=get('recheck.json'); assert (e['job_id'],e['trace_id'],e['commit'])==(r['job_id'],r['trace_id'],q['target'])
assert get('validation/validation.json')['accepted'] is True and not any(f['type']=='MISSING' for f in e['data']['findings'])
assert any(a['uri']==f"artifact://{r['job_id']}/candidate.patch" and a['sha256']==sha('candidate.patch') for a in r['artifacts'])
print('PASS accepted=true remaining_MISSING=0 patch_sha256='+sha('candidate.patch'))
PY
cat "$out/return/summary.txt"
# 未通过也保留并回传失败证据；扫描未通过则不生成可分享压缩包。
python3 labs/e13e14/scan_runtime_logs.py "$out/return" >"$out/log-scan.txt" || {
    cat "$out/log-scan.txt"
    echo '扫描未通过，请先处理，不要外发'
    exit 1
}
cp "$out/log-scan.txt" "$out/return/"
tar -C "$out/return" -czf "$out/receipt.tar.gz" .
(cd "$out" && sha256sum receipt.tar.gz >receipt.tar.gz.sha256)
printf '请回传：%s/receipt.tar.gz 和 %s/receipt.tar.gz.sha256\n' "$out" "$out"
test "$verdict" = 0
