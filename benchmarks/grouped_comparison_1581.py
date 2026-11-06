"""Grouped CSV comparison for S-Lang 1.15.81, Python and C++.

All implementations consume the same generated CSV and compute the same five
per-group metrics after the same engineer filter: count, sum, average, min,
max. Build times are reported separately. S-Lang native is measured as a
compiled executable; interpreter and Python are measured as steady-state
process runtimes. Results are normalized before comparison.
"""
from __future__ import annotations
import csv, json, re, statistics, subprocess, tempfile, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SIZES=(10_000,50_000,100_000,250_000)
REPEATS=3

SLANG='''record Scored:\n    team: Text\n    score: Number\nlet rows = read_csv("DATASET")\nselected = rows where item.role == "engineer"\nscored = selected map Scored(row.team, to_number(row.score))\ncounts = group_count(scored, "team")\nsums = group_sum(scored, "team", "score")\navgs = group_average(scored, "team", "score")\nmins = group_min(scored, "team", "score")\nmaxs = group_max(scored, "team", "score")\nshow counts\nshow sums\nshow avgs\nshow mins\nshow maxs\n'''
PY='''import csv, json\nfrom collections import OrderedDict\nrows=[]\nwith open("DATASET", newline="", encoding="utf-8") as f:\n    for r in csv.DictReader(f):\n        if r["role"] == "engineer":\n            rows.append((r["team"], int(r["score"])))\ngroups=OrderedDict()\nfor team,score in rows:\n    g=groups.setdefault(team, {"count":0,"sum":0,"min":None,"max":None})\n    g["count"] += 1; g["sum"] += score\n    g["min"] = score if g["min"] is None else min(g["min"], score)\n    g["max"] = score if g["max"] is None else max(g["max"], score)\nfor g in groups.values(): g["average"] = g["sum"] / g["count"]\nprint(json.dumps(groups, separators=(",",":")))\n'''
CPP=r'''#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <iomanip>
struct G { std::string key; long count=0; long long sum=0; long min=0; long max=0; bool init=false; };
int find(std::vector<G>& gs,const std::string& k){for(size_t i=0;i<gs.size();++i)if(gs[i].key==k)return (int)i;gs.push_back(G{k});return (int)gs.size()-1;}
int main(int argc,char**argv){std::ifstream in(argv[1]);std::string line;std::getline(in,line);std::vector<G> gs;while(std::getline(in,line)){std::stringstream ss(line);std::string name,age,score,role,team;std::getline(ss,name,',');std::getline(ss,age,',');std::getline(ss,score,',');std::getline(ss,role,',');std::getline(ss,team,',');if(!team.empty()&&team.back()=='\r')team.pop_back();if(role!="engineer")continue;long v=std::stol(score);int idx=find(gs,team);auto&g=gs[idx];g.count++;g.sum+=v;if(!g.init){g.min=g.max=v;g.init=true;}else{if(v<g.min)g.min=v;if(v>g.max)g.max=v;}}
std::cout<<"{";for(size_t i=0;i<gs.size();++i){if(i)std::cout<<",";auto&g=gs[i];std::cout<<"\""<<g.key<<"\":{"<<"\"count\":"<<g.count<<",\"sum\":"<<g.sum<<",\"average\":"<<std::setprecision(15)<<(double)g.sum/g.count<<",\"min\":"<<g.min<<",\"max\":"<<g.max<<"}";}std::cout<<"}\n";}
'''

def make_csv(path,n):
    groups={}; expected={}
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(('name','age','score','role','team'))
        for i in range(n):
            age=18+i%50; score=100+i%900; role='engineer' if i%3==0 else 'artist'; team=f'T{i%8}'
            w.writerow((f'p{i}',age,score,role,team))
            if role=='engineer':
                g=expected.setdefault(team,{'count':0,'sum':0,'min':None,'max':None}); g['count']+=1; g['sum']+=score; g['min']=score if g['min'] is None else min(g['min'],score); g['max']=score if g['max'] is None else max(g['max'],score)
    for g in expected.values(): g['average']=g['sum']/g['count']
    return expected

def same_results(a,b):
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(same_results(a[k],b[k]) for k in a)
    if isinstance(a,float) or isinstance(b,float):
        return abs(float(a)-float(b)) <= 1e-9 * max(1.0,abs(float(a)),abs(float(b)))
    return a==b

def timed(cmd):
    t=time.perf_counter(); p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True); dt=time.perf_counter()-t
    if p.returncode: raise RuntimeError(' '.join(cmd)+'\n'+p.stderr)
    return dt,p.stdout.strip()

def parse_slang(out):
    rows=[]
    for line in out.splitlines():
        for m in re.finditer(r'row\(key=([^,]+), (count|sum|average|min|max)=([^\)]+)\)',line):
            rows.append((m.group(1),m.group(2),float(m.group(3))))
    d={}
    for k,metric,v in rows:d.setdefault(k,{})[metric]=int(v) if metric in {'count','sum','min','max'} and v.is_integer() else v
    return d

def main():
    native_only = True
    with tempfile.TemporaryDirectory(prefix='slang-grouped-') as td:
        work=Path(td); cpp=work/'bench.cpp'; cpp.write_text(CPP); binary=work/'bench_cpp'
        t=time.perf_counter(); b=subprocess.run(['g++','-O2','-std=c++17',str(cpp),'-o',str(binary)],cwd=ROOT,text=True,capture_output=True); cpp_build=time.perf_counter()-t
        if b.returncode: raise RuntimeError(b.stderr)
        results=[]
        for n in SIZES:
            data=work/f'people_{n}.csv'; expected=make_csv(data,n)
            sl=work/'bench.sl'; py=work/'bench.py'; sl.write_text(SLANG.replace('DATASET',str(data))); py.write_text(PY.replace('DATASET',str(data)))
            row={'rows':n,'groups':len(expected),'expected':expected}
            runners = [('python',['python',str(py)],json.loads),('cpp',[str(binary),str(data)],json.loads)]
            if not native_only:
                runners.insert(0, ('slang_interpreter',['python','-m','slang.cli','run',str(sl)],parse_slang))
            for name,cmd,parser in runners:
                times=[]; outputs=[]
                for _ in range(REPEATS): dt,out=timed(cmd); times.append(dt); outputs.append(out)
                normalized=[parser(x) for x in outputs]
                if any(not same_results(x,expected) for x in normalized) or len(set(outputs))!=1: raise AssertionError(f'{name} mismatch {n}')
                row[name]={'median_seconds':statistics.median(times),'min_seconds':min(times),'deterministic':True}
            native=work/f'bench_native_{n}'; t=time.perf_counter(); nb=subprocess.run(['python','-m','slang.cli','build',str(sl),'-o',str(native),'--backend','native'],cwd=ROOT,text=True,capture_output=True); build=time.perf_counter()-t
            if nb.returncode: raise RuntimeError(f'native unavailable at {n}: {nb.stderr}')
            times=[]; outputs=[]
            for _ in range(REPEATS): dt,out=timed([str(native)]); times.append(dt); outputs.append(out)
            if any(not same_results(parse_slang(x),expected) for x in outputs) or len(set(outputs))!=1: raise AssertionError(f'native mismatch {n}')
            row['slang_native']={'available':True,'build_seconds':build,'median_seconds':statistics.median(times),'min_seconds':min(times),'deterministic':True}
            results.append(row)
        print(json.dumps({'repeats':REPEATS,'cpp_build_seconds':cpp_build,'results':results},indent=2))
if __name__=='__main__':main()
